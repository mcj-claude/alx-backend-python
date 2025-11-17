"""
URL configuration for messaging platform API.

Defines RESTful endpoints for conversations, messages, and user management
with proper URL patterns and routing configuration using Django REST Framework DefaultRouter.
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    UserViewSet, 
    ConversationViewSet, 
    MessageViewSet
)


# Create router for automatic URL generation
router = DefaultRouter()
router.register(r'users', UserViewSet, basename='user')
router.register(r'conversations', ConversationViewSet, basename='conversation')
router.register(r'messages', MessageViewSet, basename='message')

# URL patterns for the application
urlpatterns = [
    # Include router URLs at root level
    path('', include(router.urls)),
]

# Application name for URL namespace
app_name = 'chats'