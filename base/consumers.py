import json
from channels.generic.websocket import AsyncWebsocketConsumer

class FixtureConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.group_name = 'fixture_updates'
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    # Odbieranie eventu 'send_fixture_update'
    async def send_fixture_update(self, event):
        message = event['message']
        # Wysyłamy dalej do frontendu
        await self.send(text_data=json.dumps(message))
