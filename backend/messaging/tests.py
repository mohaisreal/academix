from unittest.mock import patch
import unittest
import asyncio
from datetime import datetime, timedelta

from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from backend.asgi import application
from users.models import User
from messaging.models import Message, MessageNotificationBatch
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

    def test_compose_without_subject_succeeds(self):
        client = APIClient()
        client.force_authenticate(user=self.student_sender)
        with self.captureOnCommitCallbacks(execute=True):
            response = client.post('/api/messaging/compose/', {
                'recipient_id': self.recipient.pk,
                'body': 'No subject here',
            }, format='json')
        self.assertEqual(response.status_code, 201)
        msg = Message.objects.get(pk=response.data['id'])
        self.assertEqual(msg.body, 'No subject here')

    def test_compose_missing_body_is_rejected(self):
        client = APIClient()
        client.force_authenticate(user=self.student_sender)
        response = client.post('/api/messaging/compose/', {
            'recipient_id': self.recipient.pk,
        }, format='json')
        self.assertEqual(response.status_code, 400)

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

    def test_opening_thread_marks_all_unread_replies_read_and_clears_badge(self):
        root = Message.objects.create(
            sender=self.student_sender,
            recipient=self.recipient,
            subject='Thread',
            body='hello',
            is_read=False,
        )
        reply_to_recipient = Message.objects.create(
            sender=self.student_sender,
            recipient=self.recipient,
            subject='Re: Thread',
            body='second message',
            parent=root,
            is_read=False,
        )
        # A reply going the OTHER direction (recipient -> sender) must be left untouched —
        # it is not "unread for the recipient", it is unread for the sender.
        reply_to_sender = Message.objects.create(
            sender=self.recipient,
            recipient=self.student_sender,
            subject='Re: Thread',
            body='my reply',
            parent=root,
            is_read=False,
        )

        client = APIClient()
        client.force_authenticate(user=self.recipient)

        unread_before = client.get('/api/messaging/unread-count/')
        self.assertEqual(unread_before.data['count'], 2)

        response = client.get(f'/api/messaging/{root.pk}/')
        self.assertEqual(response.status_code, 200)

        self.assertTrue(Message.objects.get(pk=root.pk).is_read)
        self.assertTrue(Message.objects.get(pk=reply_to_recipient.pk).is_read)
        # Untouched: this message is addressed to student_sender, not recipient.
        self.assertFalse(Message.objects.get(pk=reply_to_sender.pk).is_read)

        unread_after = client.get('/api/messaging/unread-count/')
        self.assertEqual(unread_after.data['count'], 0)

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


class MessageNotificationBatchingIntegrationTests(TestCase):
    """messaging-realtime-chat-email spec `message-notification-batching`:
    compose/reply notifications must batch within a five-minute
    recipient/thread window instead of firing on every message."""

    def setUp(self):
        self.sender = User.objects.create_user(username='batch_int_sender', email='bis@test.com', password='pass', role='s')
        self.recipient = User.objects.create_user(username='batch_int_recipient', email='bir@test.com', password='pass', role='t')
        self.client_ = APIClient()
        self.client_.force_authenticate(user=self.sender)

    @patch('messaging.views.create_notification')
    def test_second_reply_in_thread_within_window_does_not_renotify(self, mock_notify):
        with self.captureOnCommitCallbacks(execute=True):
            compose_response = self.client_.post('/api/messaging/compose/', {
                'recipient_id': self.recipient.pk,
                'subject': 'Hello',
                'body': 'first message',
            }, format='json')
        self.assertEqual(compose_response.status_code, 201)
        root_id = compose_response.data['id']
        self.assertEqual(mock_notify.call_count, 1)

        with self.captureOnCommitCallbacks(execute=True):
            reply_response = self.client_.post(f'/api/messaging/{root_id}/reply/', {
                'body': 'second message, same thread',
            }, format='json')
        # ReplyView swaps sender/recipient relative to the root, so re-authenticate
        # as the recipient to keep sending TO the original sender's thread peer.
        self.assertEqual(reply_response.status_code, 201)

        # A second message in the SAME thread within the five-minute window must
        # reuse the existing batch instead of triggering a second notification.
        self.assertEqual(mock_notify.call_count, 1)

    @patch('messaging.views.create_notification')
    def test_messages_in_different_threads_each_notify(self, mock_notify):
        other_recipient = User.objects.create_user(username='batch_int_other', email='bio@test.com', password='pass', role='t')

        with self.captureOnCommitCallbacks(execute=True):
            self.client_.post('/api/messaging/compose/', {
                'recipient_id': self.recipient.pk,
                'body': 'to recipient',
            }, format='json')
        with self.captureOnCommitCallbacks(execute=True):
            self.client_.post('/api/messaging/compose/', {
                'recipient_id': other_recipient.pk,
                'body': 'to other recipient',
            }, format='json')

        # Different recipients/threads are independent batches, so both notify.
        self.assertEqual(mock_notify.call_count, 2)

    @patch('messaging.views.create_notification')
    def test_message_after_window_notifies_again(self, mock_notify):
        with self.captureOnCommitCallbacks(execute=True):
            compose_response = self.client_.post('/api/messaging/compose/', {
                'recipient_id': self.recipient.pk,
                'subject': 'Hello',
                'body': 'first message',
            }, format='json')
        root_id = compose_response.data['id']
        self.assertEqual(mock_notify.call_count, 1)

        # Simulate the batching window having elapsed.
        MessageNotificationBatch.objects.update(
            last_message_at=timezone.now() - timedelta(minutes=6)
        )

        with self.captureOnCommitCallbacks(execute=True):
            self.client_.post(f'/api/messaging/{root_id}/reply/', {
                'body': 'second message, after the window',
            }, format='json')

        self.assertEqual(mock_notify.call_count, 2)


class MessageNotificationBatchModelTests(TestCase):
    def setUp(self):
        self.sender = User.objects.create_user(username='batch_sender', email='bs@test.com', password='pass', role='s')
        self.recipient = User.objects.create_user(username='batch_recipient', email='br@test.com', password='pass', role='t')
        self.root = Message.objects.create(
            sender=self.sender,
            recipient=self.recipient,
            subject='Root',
            body='hello',
        )

    def test_create_batch_for_recipient_and_root(self):
        batch = MessageNotificationBatch.objects.create(
            recipient=self.recipient,
            root=self.root,
        )
        self.assertEqual(batch.recipient_id, self.recipient.pk)
        self.assertEqual(batch.root_id, self.root.pk)
        self.assertIsNotNone(batch.last_message_at)

    def test_active_batch_within_window_is_found(self):
        batch = MessageNotificationBatch.objects.create(
            recipient=self.recipient,
            root=self.root,
        )
        cutoff = timezone.now() - timedelta(minutes=5)
        found = MessageNotificationBatch.objects.filter(
            recipient=self.recipient,
            root=self.root,
            last_message_at__gte=cutoff,
        ).first()
        self.assertEqual(found.pk, batch.pk)

    def test_stale_batch_outside_window_is_not_found(self):
        batch = MessageNotificationBatch.objects.create(
            recipient=self.recipient,
            root=self.root,
        )
        MessageNotificationBatch.objects.filter(pk=batch.pk).update(
            last_message_at=timezone.now() - timedelta(minutes=10)
        )
        cutoff = timezone.now() - timedelta(minutes=5)
        found = MessageNotificationBatch.objects.filter(
            recipient=self.recipient,
            root=self.root,
            last_message_at__gte=cutoff,
        ).first()
        self.assertIsNone(found)


class MessageNotificationBatchRegisterTests(TestCase):
    """Five-minute recipient/thread batching decision: messaging-realtime-chat-email
    spec `message-notification-batching` — at most one notification/email batch per
    recipient+thread within a rolling five-minute window."""

    def setUp(self):
        self.sender = User.objects.create_user(username='reg_sender', email='rs@test.com', password='pass', role='s')
        self.recipient = User.objects.create_user(username='reg_recipient', email='rr@test.com', password='pass', role='t')
        self.other_recipient = User.objects.create_user(username='reg_other', email='ro@test.com', password='pass', role='t')
        self.root = Message.objects.create(
            sender=self.sender, recipient=self.recipient, subject='Root', body='hello',
        )
        self.other_root = Message.objects.create(
            sender=self.sender, recipient=self.other_recipient, subject='Other root', body='hi',
        )

    def test_first_message_in_thread_creates_batch_and_requests_notify(self):
        batch, should_notify = MessageNotificationBatch.objects.register_message(
            recipient=self.recipient, root=self.root,
        )
        self.assertTrue(should_notify)
        self.assertEqual(batch.recipient_id, self.recipient.pk)
        self.assertEqual(batch.root_id, self.root.pk)
        self.assertEqual(MessageNotificationBatch.objects.filter(recipient=self.recipient, root=self.root).count(), 1)

    def test_second_message_within_window_reuses_batch_without_notify(self):
        first_batch, first_notify = MessageNotificationBatch.objects.register_message(
            recipient=self.recipient, root=self.root,
        )
        self.assertTrue(first_notify)

        second_batch, second_notify = MessageNotificationBatch.objects.register_message(
            recipient=self.recipient, root=self.root,
        )
        self.assertFalse(second_notify)
        self.assertEqual(second_batch.pk, first_batch.pk)
        self.assertEqual(MessageNotificationBatch.objects.filter(recipient=self.recipient, root=self.root).count(), 1)

    def test_message_after_window_creates_new_batch_and_notifies_again(self):
        first_batch, _ = MessageNotificationBatch.objects.register_message(
            recipient=self.recipient, root=self.root,
        )
        MessageNotificationBatch.objects.filter(pk=first_batch.pk).update(
            last_message_at=timezone.now() - timedelta(minutes=6)
        )

        second_batch, second_notify = MessageNotificationBatch.objects.register_message(
            recipient=self.recipient, root=self.root,
        )
        self.assertTrue(second_notify)
        self.assertNotEqual(second_batch.pk, first_batch.pk)

    def test_batches_independent_across_recipients_and_threads(self):
        _, notify_a = MessageNotificationBatch.objects.register_message(
            recipient=self.recipient, root=self.root,
        )
        _, notify_b = MessageNotificationBatch.objects.register_message(
            recipient=self.other_recipient, root=self.other_root,
        )
        self.assertTrue(notify_a)
        self.assertTrue(notify_b)
        self.assertEqual(MessageNotificationBatch.objects.count(), 2)


class UnifiedThreadListTests(TestCase):
    def setUp(self):
        self.alice = User.objects.create_user(username='alice', email='alice@test.com', password='pass', role='s')
        self.bob = User.objects.create_user(username='bob', email='bob@test.com', password='pass', role='t')
        self.carol = User.objects.create_user(username='carol', email='carol@test.com', password='pass', role='t')
        self.client = APIClient()
        self.client.force_authenticate(user=self.alice)

    def test_threads_ordered_newest_activity_first(self):
        now = timezone.now()

        # Thread A: alice -> bob, root created earliest of all messages.
        thread_a_root = Message.objects.create(
            sender=self.alice, recipient=self.bob, subject='A', body='hi bob',
        )
        Message.objects.filter(pk=thread_a_root.pk).update(created_at=now - timedelta(hours=3))
        thread_a_root.refresh_from_db()

        # Thread B: alice -> carol, root created after thread A's root.
        thread_b_root = Message.objects.create(
            sender=self.alice, recipient=self.carol, subject='B', body='hi carol',
        )
        Message.objects.filter(pk=thread_b_root.pk).update(created_at=now - timedelta(hours=2))
        thread_b_root.refresh_from_db()

        # A reply on thread A arrives after thread B's root, making thread A the
        # most recently active thread overall.
        reply = Message.objects.create(
            sender=self.bob, recipient=self.alice, subject='Re: A', body='hi alice',
            parent=thread_a_root,
        )
        Message.objects.filter(pk=reply.pk).update(created_at=now - timedelta(hours=1))
        reply.refresh_from_db()

        response = self.client.get('/api/messaging/threads/')
        self.assertEqual(response.status_code, 200)
        ids = [t['root_id'] for t in response.data]
        # Thread A's reply is the most recent activity overall, so A comes first.
        self.assertEqual(ids, [thread_a_root.pk, thread_b_root.pk])
        # Thread A's last_activity_at must reflect the reply, not its (older) root.
        last_activity_at = datetime.fromisoformat(response.data[0]['last_activity_at'])
        self.assertGreater(last_activity_at, thread_b_root.created_at)
        self.assertEqual(int(last_activity_at.timestamp()), int(reply.created_at.timestamp()))

    def test_thread_serializer_fields_and_other_participant(self):
        root = Message.objects.create(
            sender=self.alice, recipient=self.bob, subject='Hello', body='first message',
        )
        reply = Message.objects.create(
            sender=self.bob, recipient=self.alice, subject='Re: Hello', body='reply body',
            parent=root, is_read=False,
        )

        response = self.client.get('/api/messaging/threads/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)

        thread = response.data[0]
        self.assertEqual(set(thread.keys()), {
            'id', 'root_id', 'other_participant', 'last_message',
            'last_activity_at', 'unread_count',
        })
        self.assertEqual(thread['root_id'], root.pk)
        self.assertEqual(thread['other_participant']['id'], self.bob.pk)
        self.assertEqual(thread['other_participant']['username'], 'bob')
        self.assertEqual(thread['last_message']['id'], reply.pk)
        self.assertEqual(thread['last_message']['body'], 'reply body')
        self.assertEqual(thread['last_message']['sender_id'], self.bob.pk)
        self.assertEqual(thread['unread_count'], 1)

    def test_empty_inbox_returns_empty_list(self):
        response = self.client.get('/api/messaging/threads/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, [])

    def test_threads_unified_for_sender_and_recipient_roles(self):
        # alice receives from bob
        Message.objects.create(sender=self.bob, recipient=self.alice, subject='From bob', body='hi')
        # alice sends to carol
        Message.objects.create(sender=self.alice, recipient=self.carol, subject='To carol', body='hey')

        response = self.client.get('/api/messaging/threads/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 2)
        other_ids = {t['other_participant']['id'] for t in response.data}
        self.assertEqual(other_ids, {self.bob.pk, self.carol.pk})
