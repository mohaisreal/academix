from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .models import Message
from .serializers import MessageSerializer


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
        serializer = MessageSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(sender=request.user)
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
        recipient = parent.sender if parent.recipient == request.user else parent.recipient
        msg = Message.objects.create(
            sender=request.user,
            recipient=recipient,
            subject=f"Re: {parent.subject}",
            body=request.data.get('body', ''),
            parent=parent,
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
