"""
API URL configuration for the messaging platform.

Provides comprehensive URL routing with API versioning and Swagger documentation.
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
    UserProfileViewSet,
    ConversationViewSet,
    MessageViewSet,
    NotificationViewSet
)

# Create router and register ViewSets
router = DefaultRouter()
router.register(r'users', UserProfileViewSet, basename='user')
router.register(r'conversations', ConversationViewSet, basename='conversation')
router.register(r'messages', MessageViewSet, basename='message')
router.register(r'notifications', NotificationViewSet, basename='notification')

# URL patterns
urlpatterns = [
    # API Documentation
    path('schema/', SpectacularAPIView.as_view(), name='schema'),
    path('docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),
    
    # API endpoints
    path('', include(router.urls)),
    
    # Health check endpoint
    path('health/', include('health_check.urls')),
    
    # Authentication endpoints (handled by DRF)
    path('auth/', include('rest_framework.urls')),
]

# Schema view for API documentation
schema_view = get_schema_view(
    title='Messaging Platform API',
    description='A comprehensive messaging platform API built with Django REST Framework',
    version='1.0.0',
    patterns=urlpatterns,
    urlconf='api.urls',
    public=True,
    permission_classes=[],
)