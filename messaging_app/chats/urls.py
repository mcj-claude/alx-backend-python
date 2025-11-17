"""
URL configuration for messaging platform API.

Defines RESTful endpoints for conversations, messages, and user management
with proper URL patterns and routing configuration.
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework.schemas import get_schema_view
from drf_spectacular.views import (
    SpectacularAPIView, 
    SpectacularRedocView, 
    SpectacularSwaggerView
)

from .views import (
    UserViewSet, 
    ConversationViewSet, 
    MessageViewSet,
    ConversationMessagesViewSet
)
from .views import *  # Import all views for reference


# Create router for automatic URL generation
router = DefaultRouter()
router.register(r'users', UserViewSet, basename='user')
router.register(r'conversations', ConversationViewSet, basename='conversation')
router.register(r'messages', MessageViewSet, basename='message')

# API v1 URL patterns
urlpatterns = [
    # API Documentation
    path('docs/', SpectacularAPIView.as_view(), name='schema'),
    path('docs/swagger-ui/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('docs/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),
    
    # API v1 endpoints
    path('v1/', include(router.urls)),
    
    # Nested conversation messages endpoints
    path('v1/conversations/<uuid:conversation_id>/messages/', 
         ConversationMessagesViewSet.as_view({
             'get': 'list',
             'post': 'create'
         }), 
         name='conversation-messages'),
    
    # Direct conversation endpoints (additional to router)
    path('v1/conversations/<uuid:conversation_id>/', 
         ConversationViewSet.as_view({
             'get': 'retrieve',
         }), 
         name='conversation-detail'),
    
    # Individual message endpoints
    path('v1/messages/<uuid:message_id>/', 
         MessageViewSet.as_view({
             'get': 'retrieve',
             'put': 'update',
             'patch': 'partial_update',
             'delete': 'destroy'
         }), 
         name='message-detail'),
    
    # User-specific endpoints
    path('v1/users/me/', 
         UserViewSet.as_view({
             'get': 'me'
         }), 
         name='user-me'),
    
    # User search endpoints
    path('v1/users/search/', 
         UserViewSet.as_view({
             'get': 'list'
         }), 
         name='user-search'),
]

# Additional URL patterns for conversation management
conversation_urlpatterns = [
    # Conversation participant management
    path('v1/conversations/<uuid:conversation_id>/participants/add/', 
         ConversationViewSet.as_view({
             'post': 'add_participant'
         }), 
         name='conversation-add-participant'),
    
    path('v1/conversations/<uuid:conversation_id>/participants/remove/', 
         ConversationViewSet.as_view({
             'post': 'remove_participant'
         }), 
         name='conversation-remove-participant'),
    
    # Message-specific actions
    path('v1/messages/<uuid:message_id>/mark-read/', 
         MessageViewSet.as_view({
             'post': 'mark_read'
         }), 
         name='message-mark-read'),
]

# User management URL patterns
user_urlpatterns = [
    # User profile endpoints
    path('v1/users/<uuid:user_id>/profile/', 
         UserViewSet.as_view({
             'get': 'retrieve'
         }), 
         name='user-profile'),
    
    # User conversation endpoints
    path('v1/users/me/conversations/', 
         ConversationViewSet.as_view({
             'get': 'list'
         }), 
         name='user-conversations'),
]

# Schema view for API documentation
schema_view = get_schema_view(
    title="Messaging Platform API",
    description="A comprehensive REST API for managing conversations, messages, and users",
    version="1.0.0",
    patterns=[
        path('v1/', include([
            path('', include(router.urls)),
            path('conversations/<uuid:conversation_id>/messages/', include(conversation_urlpatterns)),
            path('users/', include(user_urlpatterns)),
        ])),
    ],
    url='http://localhost:8000/api/',
)

# Combined URL patterns
api_urlpatterns = urlpatterns + conversation_urlpatterns + user_urlpatterns

# Main URL patterns
urlpatterns = [
    # API documentation
    path('api/schema/', schema_view),
    
    # API endpoints
    path('api/', include(api_urlpatterns)),
    
    # Alternative documentation endpoints
    path('api/docs/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/swagger-ui/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/docs/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),
]

# Additional helper functions for URL generation
def get_conversation_messages_url(conversation_id):
    """Generate URL for conversation messages endpoint."""
    return f'/api/v1/conversations/{conversation_id}/messages/'

def get_message_detail_url(message_id):
    """Generate URL for individual message endpoint."""
    return f'/api/v1/messages/{message_id}/'

def get_conversation_detail_url(conversation_id):
    """Generate URL for conversation detail endpoint."""
    return f'/api/v1/conversations/{conversation_id}/'

def get_user_profile_url(user_id):
    """Generate URL for user profile endpoint."""
    return f'/api/v1/users/{user_id}/'

# URL pattern names for reverse URL lookup
url_pattern_names = {
    # Core endpoints
    'conversation-list': 'conversation-list',
    'conversation-detail': 'conversation-detail',
    'conversation-messages': 'conversation-messages',
    'message-list': 'message-list',
    'message-detail': 'message-detail',
    'user-list': 'user-list',
    'user-detail': 'user-detail',
    'user-me': 'user-me',
    
    # Action endpoints
    'conversation-add-participant': 'conversation-add-participant',
    'conversation-remove-participant': 'conversation-remove-participant',
    'message-mark-read': 'message-mark-read',
    
    # Documentation
    'api-schema': 'schema',
    'api-swagger-ui': 'swagger-ui',
    'api-redoc': 'redoc',
}

# Export URL patterns for Django
app_name = 'chats'

# For debugging and development - print URL patterns
if __name__ == '__main__':
    print("Messaging Platform API URL Patterns:")
    print("=" * 50)
    for pattern in urlpatterns:
        if hasattr(pattern, 'pattern'):
            print(f"Pattern: {pattern.pattern}")
            print(f"Name: {pattern.name}")
            print("-" * 30)
    
    print("\nRouter URLs:")
    print("=" * 50)
    for route in router.urls:
        print(f"Route: {route.pattern}")
        print(f"Base name: {route.name}")
        print("-" * 30)