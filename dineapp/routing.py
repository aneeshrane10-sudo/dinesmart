"""
WebSocket URL routing for the occupancy detection system.
"""

from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    re_path(r'ws/occupancy/(?P<restaurant_id>\w+)/$', consumers.OccupancyConsumer.as_asgi()),
]
