"""
URL configuration for messaging platform API.

Defines RESTful endpoints for conversations, messages, and user management
with proper URL patterns and routing configuration using Django REST Framework NestedDefaultRouter.
"""

from django.urls import path, include
from rest_framework_nested.routers import NestedDefaultRouter
from rest_framework.routers import DefaultRouter

from .views import (
    UserViewSet,
    ConversationViewSet,
    MessageViewSet
)


# Create main router for automatic URL generation
router = DefaultRouter()
router.register(r'users', UserViewSet, basename='user')
router.register(r'conversations', ConversationViewSet, basename='conversation')
router.register(r'messages', MessageViewSet, basename='message')

# Create nested router for messages within conversations
nested_router = NestedDefaultRouter(router, r'conversations', lookup='conversation')
nested_router.register(r'messages', MessageViewSet, basename='conversation-messages')

# URL patterns for the application
urlpatterns = [
    # Include main router URLs at root level
    path('', include(router.urls)),
    # Include nested router URLs for conversation messages
    path('', include(nested_router.urls)),
]

# Application name for URL namespace
app_name = 'chats'