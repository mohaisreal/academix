from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Q
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .models import Message, MessageNotificationBatch
from .serializers import MessageSerializer, ThreadSerializer
from notifications.utils import create_notification
from .realtime import broadcast_message_created

User = get_user_model()


def _notify_recipient_of_new_message(msg, *, sender, root):
    """
    Notify ``msg.recipient`` about a new message/reply, batching alerts so at
    most one notification/email goes out per recipient/thread within the
    five-minute window (message-notification-batching spec).
    """
    if msg.recipient_id == sender.pk:
        return

    _, should_notify = MessageNotificationBatch.objects.register_message(
        recipient=msg.recipient, root=root,
    )
    if not should_notify:
        return

    sender_name = sender.get_full_name() or sender.username
    create_notification(
        user=msg.recipient,
        title='Nuevo mensaje recibido',
        message=f'Has recibido un mensaje de {sender_name}: {msg.subject}',
        notif_type='info',
        event_type='message_received',
        context={
            'sender_name': sender_name,
            'message_subject': msg.subject,
            'message_preview': msg.body[:240],
        },
    )


class InboxView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        msgs = Message.objects.filter(
            recipient=request.user, is_deleted_by_recipient=False, parent=None
        ).select_related('sender', 'recipient')
        return Response(MessageSerializer(msgs, many=True).data)


class SentView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        msgs = Message.objects.filter(
            sender=request.user, is_deleted_by_sender=False, parent=None
        ).select_related('sender', 'recipient')
        return Response(MessageSerializer(msgs, many=True).data)


class ThreadListView(APIView):
    """
    Unified inbox: one entry per thread (root message) the user can see,
    whether they are the sender or recipient of the root, ordered newest
    first by latest activity across the root and its replies.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        roots = Message.objects.filter(
            Q(sender=user, is_deleted_by_sender=False)
            | Q(recipient=user, is_deleted_by_recipient=False),
            parent=None,
        ).select_related('sender', 'recipient')

        threads = []
        for root in roots:
            thread_messages = list(
                Message.objects.filter(Q(pk=root.pk) | Q(parent=root))
                .select_related('sender', 'recipient')
            )
            last_message = max(thread_messages, key=lambda m: (m.created_at, m.pk))
            unread_count = sum(
                1 for m in thread_messages
                if m.recipient_id == user.pk and not m.is_read and not m.is_deleted_by_recipient
            )
            other_participant = root.recipient if root.sender_id == user.pk else root.sender

            threads.append({
                'id': root.pk,
                'root_id': root.pk,
                'other_participant': other_participant,
                'last_message': {
                    'id': last_message.pk,
                    'body': last_message.body,
                    'sender_id': last_message.sender_id,
                    'created_at': last_message.created_at,
                },
                'last_activity_at': last_message.created_at,
                'unread_count': unread_count,
            })

        threads.sort(key=lambda t: (t['last_activity_at'], t['root_id']), reverse=True)
        return Response(ThreadSerializer(threads, many=True).data)


class ComposeView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        data = request.data.copy()
        recipient_lookup = data.get('recipient')

        # Entrada retrocompatible: permite que la interfaz envíe un valor numérico
        # ID de usuario o nombre de usuario/correo en "recipient". El contrato del serializador es
        # sigue siendo recipient_id; este mapeo mantiene la API explícita internamente.
        if not data.get('recipient_id') and recipient_lookup:
            recipient_lookup = str(recipient_lookup).strip()
            if recipient_lookup.isdigit():
                data['recipient_id'] = int(recipient_lookup)
            else:
                recipient = (
                    User.objects
                    .filter(username__iexact=recipient_lookup)
                    .first()
                    or User.objects.filter(email__iexact=recipient_lookup).first()
                )
                if not recipient:
                    return Response(
                        {'recipient': 'Recipient user was not found.'},
                        status=400,
                    )
                data['recipient_id'] = recipient.pk

        serializer = MessageSerializer(data=data)
        if serializer.is_valid():
            msg = serializer.save(sender=request.user)
            transaction.on_commit(lambda: broadcast_message_created(msg))
            _notify_recipient_of_new_message(msg, sender=request.user, root=msg)
            return Response(serializer.data, status=201)
        return Response(serializer.errors, status=400)


class MessageThreadView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        try:
            msg = Message.objects.get(pk=pk)
        except Message.DoesNotExist:
            return Response({'error': 'Not found'}, status=404)
        if msg.sender != request.user and msg.recipient != request.user:
            return Response({'error': 'Forbidden'}, status=403)

        # Opening a thread clears ALL of the requesting participant's unread
        # messages in that thread (root + replies), not just the message
        # fetched by `pk`. Without this, replies the recipient hasn't viewed
        # individually keep counting toward the unread badge forever.
        root_id = msg.parent_id or msg.pk
        Message.objects.filter(
            Q(pk=root_id) | Q(parent_id=root_id),
            recipient=request.user,
            is_read=False,
        ).update(is_read=True)

        msg.refresh_from_db()
        replies = Message.objects.filter(parent_id=root_id).select_related('sender', 'recipient')
        return Response({
            'message': MessageSerializer(msg).data,
            'replies': MessageSerializer(replies, many=True).data,
        })

    def delete(self, request, pk):
        try:
            msg = Message.objects.get(pk=pk)
        except Message.DoesNotExist:
            return Response({'error': 'Not found'}, status=404)
        if msg.sender == request.user:
            msg.is_deleted_by_sender = True
        elif msg.recipient == request.user:
            msg.is_deleted_by_recipient = True
        else:
            return Response({'error': 'Forbidden'}, status=403)
        msg.save()
        return Response({'status': 'deleted'})


class ReplyView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        try:
            parent = Message.objects.get(pk=pk)
        except Message.DoesNotExist:
            return Response({'error': 'Not found'}, status=404)

        if parent.sender != request.user and parent.recipient != request.user:
            return Response({'error': 'Forbidden'}, status=403)

        body = str(request.data.get('body', '')).strip()
        if not body:
            return Response({'body': 'Reply body is required.'}, status=400)

        recipient = parent.sender if parent.recipient == request.user else parent.recipient
        msg = Message.objects.create(
            sender=request.user,
            recipient=recipient,
            subject=f"Re: {parent.subject}",
            body=body,
            parent=parent,
        )
        transaction.on_commit(lambda: broadcast_message_created(msg))
        root = parent.parent if parent.parent_id else parent
        _notify_recipient_of_new_message(msg, sender=request.user, root=root)
        return Response(MessageSerializer(msg).data, status=201)


class MarkMessageReadView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, pk):
        try:
            msg = Message.objects.get(pk=pk, recipient=request.user)
        except Message.DoesNotExist:
            return Response({'error': 'Not found'}, status=404)
        msg.is_read = True
        msg.save()
        return Response(MessageSerializer(msg).data)


class UnreadMessageCountView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        count = Message.objects.filter(
            recipient=request.user, is_read=False, is_deleted_by_recipient=False
        ).count()
        return Response({'count': count})
