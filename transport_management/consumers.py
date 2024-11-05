import json
from channels.generic.websocket import AsyncWebsocketConsumer

class TripStatusConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.trip_id = self.scope['url_route']['kwargs']['trip_id']
        self.group_name = f'trip_status_{self.trip_id}'

        # Rejoindre le groupe
        await self.channel_layer.group_add(
            self.group_name,
            self.channel_name
        )

        await self.accept()

    async def disconnect(self, close_code):
        # Quitter le groupe
        await self.channel_layer.group_discard(
            self.group_name,
            self.channel_name
        )

    # Recevoir des messages du groupe
    async def send_status(self, event):
        status = event['status']
        await self.send(text_data=json.dumps(status))
