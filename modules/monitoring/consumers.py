from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer

from .services import DISPLAY_GROUP, display_payload


class DisplayConsumer(AsyncJsonWebsocketConsumer):
    """Public, push-only LCD feed: full state on connect, then a new state on every change."""

    async def connect(self):
        await self.channel_layer.group_add(DISPLAY_GROUP, self.channel_name)
        await self.accept()
        await self.send_json(await database_sync_to_async(display_payload)())

    async def disconnect(self, code):
        await self.channel_layer.group_discard(DISPLAY_GROUP, self.channel_name)

    async def receive_json(self, content, **kwargs):
        pass  # screens never talk back

    async def display_update(self, event):
        await self.send_json(event["data"])
