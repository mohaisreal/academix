import json

try:
    from channels.generic.websocket import AsyncWebsocketConsumer
except ModuleNotFoundError:  # pragma: no cover - fallback when channels isn't installed locally
    class AsyncWebsocketConsumer:
        async def accept(self):
            return None

        async def close(self, code=None):
            return None

        async def send(self, text_data=None, bytes_data=None):
            return None


class MessagingConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        user = self.scope.get('user')
        if not user or not user.is_authenticated:
            await self.close(code=4401)
            return
        self.group_name = f'messaging.user.{user.pk}'
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        group_name = getattr(self, 'group_name', None)
        if group_name:
            await self.channel_layer.group_discard(group_name, self.channel_name)

    async def message_created(self, event):
        await self.send(text_data=json.dumps(event['payload']))
