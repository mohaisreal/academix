try:
    from asgiref.sync import async_to_sync
    from channels.layers import get_channel_layer
except ModuleNotFoundError:  # pragma: no cover - fallback when channels isn't installed locally
    async_to_sync = None
    get_channel_layer = lambda: None


def broadcast_message_created(message):
    channel_layer = get_channel_layer()
    if channel_layer is None or async_to_sync is None:
        return

    payload = {
        'type': 'message.created',
        'message_id': message.pk,
        'root_id': message.parent_id or message.pk,
        'sender_id': message.sender_id,
        'recipient_id': message.recipient_id,
        'created_at': message.created_at.isoformat(),
    }
    for user_id in {message.sender_id, message.recipient_id}:
        async_to_sync(channel_layer.group_send)(
            f'messaging.user.{user_id}',
            {'type': 'message.created', 'payload': payload},
        )
