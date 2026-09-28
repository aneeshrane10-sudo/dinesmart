"""
WebSocket Consumer for real-time occupancy updates.
Uses Django Channels to push live status changes to the dashboard.
"""

import json
import logging
from channels.generic.websocket import AsyncWebsocketConsumer

logger = logging.getLogger(__name__)


class OccupancyConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for real-time occupancy updates.
    Clients join a restaurant-specific group and receive status updates.
    """

    async def connect(self):
        self.restaurant_id = self.scope['url_route']['kwargs'].get('restaurant_id', 'default')
        self.group_name = f"occupancy_{self.restaurant_id}"

        # Join the occupancy group
        await self.channel_layer.group_add(
            self.group_name,
            self.channel_name
        )
        await self.accept()
        logger.info(f"WebSocket connected: {self.group_name}")

    async def disconnect(self, code: int):
        # Leave the group
        await self.channel_layer.group_discard(
            self.group_name,
            self.channel_name
        )
        logger.info(f"WebSocket disconnected: {self.group_name}")

    async def receive(self, text_data: str | None = None, bytes_data: bytes | None = None):
        """Handle incoming messages from the client (e.g., ping/pong)."""
        if text_data is None:
            return

        try:
            data = json.loads(text_data)
            msg_type = data.get('type', '')

            if msg_type == 'ping':
                await self.send(text_data=json.dumps({'type': 'pong'}))

        except json.JSONDecodeError:
            pass

    async def occupancy_update(self, event):
        """Send occupancy status update to the client."""
        await self.send(text_data=json.dumps({
            'type': 'occupancy_update',
            'data': event.get('data', {}),
        }))

    async def frame_update(self, event):
        """Send annotated frame update to the client."""
        await self.send(text_data=json.dumps({
            'type': 'frame_update',
            'frame': event.get('frame', ''),
        }))
