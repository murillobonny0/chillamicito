"""
ASGI config for config project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/6.0/howto/deployment/asgi/
"""

import os

from channels.auth import AuthMiddlewareStack
from channels.routing import ProtocolTypeRouter, URLRouter
from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

django_asgi_app = get_asgi_application()

from usuarios.routing import websocket_urlpatterns

# ASGI permite atender peticiones HTTP normales y conexiones WebSocket.
application = ProtocolTypeRouter(
    {
        # Rutas REST de Django y Django REST Framework.
        'http': django_asgi_app,
        # Canal en tiempo real para alertas de stock y feriados.
        'websocket': AuthMiddlewareStack(URLRouter(websocket_urlpatterns)),
    }
)
