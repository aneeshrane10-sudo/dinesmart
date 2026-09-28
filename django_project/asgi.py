"""
ASGI config for django_project project — upgraded to support Django Channels WebSockets.
"""

import os

from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'django_project.settings')

from dineapp.routing import websocket_urlpatterns

application = ProtocolTypeRouter({
    # Standard HTTP requests → Django
    "http": get_asgi_application(),

    # WebSocket requests → Channels consumers (with session/auth middleware)
    "websocket": AuthMiddlewareStack(
        URLRouter(websocket_urlpatterns)
    ),
})
