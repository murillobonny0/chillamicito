import json

from channels.generic.websocket import AsyncWebsocketConsumer


class NotificacionConsumer(AsyncWebsocketConsumer):
    """Canal WebSocket que envia alertas nuevas a la interfaz en tiempo real."""

    group_name = 'notificaciones_stock'

    async def connect(self):
        """Agrega el navegador conectado al grupo de notificaciones."""
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        """Quita el navegador del grupo cuando se cierra la conexion."""
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def notificacion_stock(self, event):
        """Envia al frontend el JSON de la alerta recibida desde el backend."""
        await self.send(text_data=json.dumps(event['data']))

    async def movimiento_stock(self, event):
        """Envia al frontend el aviso de un movimiento guardado en el servidor."""
        await self.send(text_data=json.dumps(event['data']))
