"""
WebSocket routing configuration for real-time messaging.

Handles WebSocket connections for real-time message delivery and live updates.
"""

from django.urls import re_path

websocket_urlpatterns = [
    # WebSocket routing will be implemented in the consumers module
    re_path(r'ws/chat/(?P<conversation_id>[^/]+)/$', None),
    re_path(r'ws/notifications/$', None),
    re_path(r'ws/status/$', None),
]