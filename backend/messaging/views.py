from django.contrib.auth import get_user_model
from django.db import transaction
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .models import Message
from .serializers import MessageSerializer
from notifications.utils import create_notification
from .realtime import broadcast_message_created

User = get_user_model()


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
            if msg.recipient != request.user:
                sender_name = request.user.get_full_name() or request.user.username
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
        if msg.recipient == request.user and not msg.is_read:
            msg.is_read = True
            msg.save()
        replies = Message.objects.filter(parent=msg).select_related('sender', 'recipient')
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
        if recipient != request.user:
            sender_name = request.user.get_full_name() or request.user.username
            create_notification(
                user=recipient,
                title='Nueva respuesta recibida',
                message=f'Has recibido una respuesta de {sender_name}: {parent.subject}',
                notif_type='info',
                event_type='message_received',
                context={
                    'sender_name': sender_name,
                    'message_subject': msg.subject,
                    'message_preview': msg.body[:240],
                },
            )
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
