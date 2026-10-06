from django.urls import path

from .consumers import NotificacionConsumer


websocket_urlpatterns = [
    # Ruta usada por React para recibir alertas en tiempo real.
    path('ws/notificaciones/', NotificacionConsumer.as_asgi()),
]
