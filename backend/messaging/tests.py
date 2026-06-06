from unittest.mock import patch
import unittest
import asyncio

from django.test import TestCase, override_settings
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from backend.asgi import application
from users.models import User
from messaging.models import Message
from messaging.realtime import broadcast_message_created

try:
    from channels.testing import WebsocketCommunicator
    CHANNELS_AVAILABLE = True
except ModuleNotFoundError:
    WebsocketCommunicator = None
    CHANNELS_AVAILABLE = False


class MessagingRealtimeTests(TestCase):
    def setUp(self):
        self.student_sender = User.objects.create_user(username='student_sender', email='s@test.com', password='pass', role='s')
        self.teacher_sender = User.objects.create_user(username='teacher_sender', email='t@test.com', password='pass', role='t')
        self.management_sender = User.objects.create_user(username='management_sender', email='m@test.com', password='pass', role='m')
        self.admin_sender = User.objects.create_user(username='admin_sender', email='a@test.com', password='pass', role='a')
        self.recipient = User.objects.create_user(username='recipient', email='r@test.com', password='pass', role='s')

    @override_settings(CHANNEL_LAYERS={'default': {'BACKEND': 'channels.layers.InMemoryChannelLayer'}})
    @unittest.skipUnless(CHANNELS_AVAILABLE, 'channels not installed')
    async def test_websocket_rejects_anonymous(self):
        communicator = WebsocketCommunicator(application, '/ws/messaging/')
        connected, _ = await communicator.connect()
        self.assertFalse(connected)

    @override_settings(CHANNEL_LAYERS={'default': {'BACKEND': 'channels.layers.InMemoryChannelLayer'}})
    @unittest.skipUnless(CHANNELS_AVAILABLE, 'channels not installed')
    async def test_websocket_accepts_valid_jwt(self):
        token = AccessToken.for_user(self.student_sender)
        communicator = WebsocketCommunicator(application, f'/ws/messaging/?token={str(token)}')
        connected, _ = await communicator.connect()
        self.assertTrue(connected)
        await communicator.disconnect()

    def test_compose_all_roles_can_send_and_broadcast(self):
        roles = [self.student_sender, self.teacher_sender, self.management_sender, self.admin_sender]
        for sender in roles:
            with self.subTest(role=sender.role):
                client = APIClient()
                client.force_authenticate(user=sender)
                with self.captureOnCommitCallbacks(execute=True):
                    response = client.post('/api/messaging/compose/', {
                        'recipient_id': self.recipient.pk,
                        'subject': f'Hello from {sender.username}',
                        'body': 'Hi there',
                    }, format='json')
                self.assertEqual(response.status_code, 201)
                self.assertTrue(Message.objects.filter(subject=f'Hello from {sender.username}').exists())

    @patch('messaging.realtime.get_channel_layer')
    @patch('messaging.realtime.async_to_sync', side_effect=lambda fn: (lambda *args, **kwargs: asyncio.run(fn(*args, **kwargs))))
    def test_broadcast_is_participant_scoped_and_minimal(self, mock_sync, mock_layer):
        class Layer:
            def __init__(self):
                self.calls = []

            async def group_send(self, group, message):
                self.calls.append((group, message))

        layer = Layer()
        mock_layer.return_value = layer

        message = Message.objects.create(
            sender=self.student_sender,
            recipient=self.recipient,
            subject='Scoped',
            body='hello',
        )
        broadcast_message_created(message)

        self.assertEqual({group for group, _ in layer.calls}, {f'messaging.user.{self.student_sender.pk}', f'messaging.user.{self.recipient.pk}'})
        for _, payload in layer.calls:
            self.assertEqual(set(payload.keys()), {'type', 'payload'})
            self.assertEqual(payload['type'], 'message.created')
            self.assertEqual(set(payload['payload'].keys()), {'type', 'message_id', 'root_id', 'sender_id', 'recipient_id', 'created_at'})

    def test_thread_access_denied_for_non_participant(self):
        message = Message.objects.create(
            sender=self.student_sender,
            recipient=self.recipient,
            subject='Thread',
            body='hello',
        )
        client = APIClient()
        outsider = User.objects.create_user(username='outsider', email='o@test.com', password='pass', role='t')
        client.force_authenticate(user=outsider)
        response = client.get(f'/api/messaging/{message.pk}/')
        self.assertEqual(response.status_code, 403)

    def test_thread_marks_read_for_recipient_only(self):
        message = Message.objects.create(
            sender=self.student_sender,
            recipient=self.recipient,
            subject='Thread',
            body='hello',
            is_read=False,
        )
        client = APIClient()
        client.force_authenticate(user=self.recipient)
        response = client.get(f'/api/messaging/{message.pk}/')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(Message.objects.get(pk=message.pk).is_read)

    def test_reply_denied_for_non_participant(self):
        parent = Message.objects.create(
            sender=self.student_sender,
            recipient=self.recipient,
            subject='Thread',
            body='hello',
        )
        outsider = User.objects.create_user(username='outsider2', email='o2@test.com', password='pass', role='a')
        client = APIClient()
        client.force_authenticate(user=outsider)
        response = client.post(f'/api/messaging/{parent.pk}/reply/', {'body': 'nope'}, format='json')
        self.assertEqual(response.status_code, 403)

    def test_unread_count_and_mark_read_flow(self):
        unread_msg = Message.objects.create(
            sender=self.student_sender,
            recipient=self.recipient,
            subject='Unread',
            body='hello',
            is_read=False,
        )
        read_msg = Message.objects.create(
            sender=self.student_sender,
            recipient=self.recipient,
            subject='Read',
            body='world',
            is_read=True,
        )

        client = APIClient()
        client.force_authenticate(user=self.recipient)

        unread_response = client.get('/api/messaging/unread-count/')
        self.assertEqual(unread_response.status_code, 200)
        self.assertEqual(unread_response.data['count'], 1)

        mark_response = client.patch(f'/api/messaging/{read_msg.pk}/mark-read/', format='json')
        self.assertEqual(mark_response.status_code, 200)
        self.assertTrue(mark_response.data['is_read'])
        self.assertEqual(Message.objects.get(pk=unread_msg.pk).is_read, False)
