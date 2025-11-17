"""
Comprehensive ViewSets for the messaging platform API.

Provides advanced ViewSet implementations with custom actions, filtering,
pagination, and optimized database queries.
"""

from rest_framework import viewsets, status, mixins
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Q, Count, Max, Avg
from django.utils import timezone
from django.shortcuts import get_object_or_404
import logging

from .permissions import (
    IsAuthenticated as CustomIsAuthenticated, IsOwnerOrReadOnly, IsParticipant,
    CanEditMessage, CanDeleteMessage, IsAdminUser, RateLimitPermission,
    IsActiveUser, IsVerifiedUser
)
from .serializers import (
    UserProfileSerializer, UserListSerializer, ConversationListSerializer,
    ConversationDetailSerializer, MessageSerializer, MessageListSerializer,
    NotificationSerializer, NotificationListSerializer
)
from .exceptions import raise_not_found, raise_permission_error, raise_validation_error
from ..models import (
    User, Conversation, Message, MessageThread, MessageAttachment,
    Notification
)

logger = logging.getLogger(__name__)


class BaseAPIViewSet(viewsets.ModelViewSet):
    """
    Base ViewSet class with common functionality and optimizations.
    
    Provides caching, query optimization, and common response patterns.
    """
    
    permission_classes = [IsAuthenticated, IsActiveUser]
    filter_backends = [DjangoFilterBackend]
    
    def get_serializer_class(self):
        """Override in subclasses to provide appropriate serializer."""
        return super().get_serializer_class()
    
    def get_queryset(self):
        """Override in subclasses to provide optimized querysets."""
        return super().get_queryset()
    
    def get_permissions(self):
        """Get permissions for the current action."""
        if hasattr(self, 'action_permissions'):
            return [permission() for permission in self.action_permissions.get(self.action, self.permission_classes)]
        return super().get_permissions()
    
    def list(self, request, *args, **kwargs):
        """Override list method to add metadata and performance optimization."""
        queryset = self.filter_queryset(self.get_queryset())
        
        # Add pagination
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(queryset, many=True)
        
        # Add metadata
        response_data = {
            'results': serializer.data,
            'count': queryset.count() if hasattr(queryset, 'count') else len(serializer.data),
            'page': None,  # Will be set by pagination
            'page_size': self.pagination_class.page_size if self.paginator else len(serializer.data)
        }
        
        return Response(response_data)
    
    def retrieve(self, request, *args, **kwargs):
        """Override retrieve method with detailed logging."""
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        
        # Log access for audit purposes
        logger.info(f"Retrieved {self.__class__.__name__} {instance.id} by user {request.user.id}")
        
        return Response(serializer.data)
    
    def perform_create(self, serializer):
        """Override create to add logging and custom behavior."""
        instance = serializer.save()
        logger.info(f"Created {self.__class__.__name__} {instance.id} by user {self.request.user.id}")
    
    def perform_update(self, serializer):
        """Override update to add logging."""
        instance = serializer.save()
        logger.info(f"Updated {self.__class__.__name__} {instance.id} by user {self.request.user.id}")
    
    def perform_destroy(self, instance):
        """Override destroy to add logging."""
        logger.info(f"Deleted {self.__class__.__name__} {instance.id} by user {self.request.user.id}")
        instance.delete()


class UserProfileViewSet(BaseAPIViewSet):
    """
    ViewSet for user profile management.
    
    Provides CRUD operations for user profiles with advanced filtering and actions.
    """
    
    serializer_class = UserProfileSerializer
    queryset = User.objects.all().prefetch_related()
    
    action_permissions = {
        'list': [CustomIsAuthenticated],
        'retrieve': [CustomIsAuthenticated],
        'me': [CustomIsAuthenticated],
        'online_users': [CustomIsAuthenticated],
        'search': [CustomIsAuthenticated]
    }
    
    filterset_fields = {
        'is_active': ['exact'],
        'is_verified': ['exact'],
        'preferred_language': ['exact', 'icontains'],
        'timezone': ['exact', 'icontains'],
        'created_at': ['gte', 'lte', 'date'],
    }
    
    search_fields = ['username', 'email', 'first_name', 'last_name']
    
    def get_queryset(self):
        """Provide optimized queryset with select_related and prefetch."""
        return User.objects.select_related().prefetch_related(
            'conversations', 'sent_messages', 'received_messages'
        ).order_by('-last_seen', '-created_at')
    
    @action(detail=False, methods=['get'])
    def me(self, request):
        """Get current user's profile information."""
        serializer = self.get_serializer(request.user)
        return Response(serializer.data)
    
    @action(detail=False, methods=['post'])
    def search(self, request):
        """Search users by various criteria."""
        query = request.data.get('query', '').strip()
        limit = request.data.get('limit', 20)
        
        if not query:
            raise_validation_error("Search query is required")
        
        # Search users
        users = User.objects.filter(
            Q(username__icontains=query) |
            Q(email__icontains=query) |
            Q(first_name__icontains=query) |
            Q(last_name__icontains=query)
        ).filter(is_active=True).order_by('username')[:limit]
        
        serializer = UserListSerializer(users, many=True)
        return Response({'results': serializer.data, 'count': len(serializer.data)})
    
    @action(detail=False, methods=['get'])
    def online_users(self, request):
        """Get list of currently online users."""
        since_time = timezone.now() - timezone.timedelta(minutes=5)
        users = User.objects.filter(
            last_seen__gte=since_time,
            show_online_status=True,
            is_active=True
        ).order_by('-last_seen')[:50]
        
        serializer = UserListSerializer(users, many=True)
        return Response({'results': serializer.data, 'count': len(serializer.data)})
    
    @action(detail=True, methods=['post'])
    def update_last_seen(self, request, pk=None):
        """Update user's last seen timestamp."""
        user = self.get_object()
        
        # Only allow users to update their own status
        if user != request.user and not request.user.is_staff:
            raise_permission_error("You can only update your own status")
        
        user.update_last_seen()
        return Response({'status': 'updated', 'last_seen': user.last_seen})
    
    @action(detail=True, methods=['post'])
    def block(self, request, pk=None):
        """Block a user from contacting the current user."""
        # Implementation for user blocking would go here
        # This is a placeholder for the blocking functionality
        return Response({'status': 'blocked', 'user_id': pk})
    
    @action(detail=True, methods=['post'])
    def unblock(self, request, pk=None):
        """Unblock a user."""
        # Implementation for unblocking would go here
        return Response({'status': 'unblocked', 'user_id': pk})


class ConversationViewSet(BaseAPIViewSet):
    """
    ViewSet for conversation management.
    
    Provides CRUD operations for conversations with participant management,
    message handling, and advanced filtering.
    """
    
    serializer_class = ConversationDetailSerializer
    queryset = Conversation.objects.select_related('created_by').prefetch_related(
        'participants', 'messages', 'messages__sender', 'messages__attachments'
    )
    
    action_permissions = {
        'list': [CustomIsAuthenticated],
        'retrieve': [CustomIsAuthenticated, IsParticipant],
        'create': [CustomIsAuthenticated],
        'update': [CustomIsAuthenticated, IsParticipant],
        'destroy': [CustomIsAuthenticated, IsParticipant],
        'messages': [CustomIsAuthenticated, IsParticipant],
        'add_participant': [CustomIsAuthenticated, IsParticipant],
        'remove_participant': [CustomIsAuthenticated, IsParticipant],
        'mark_as_read': [CustomIsAuthenticated, IsParticipant],
        'archive': [CustomIsAuthenticated, IsParticipant],
        'leave': [CustomIsAuthenticated, IsParticipant],
        'join': [CustomIsAuthenticated]
    }
    
    filterset_fields = {
        'conversation_type': ['exact'],
        'status': ['exact'],
        'is_active': ['exact'],
        'created_at': ['gte', 'lte', 'date'],
        'last_message_at': ['gte', 'lte', 'date'],
    }
    
    search_fields = ['name', 'description', 'participants__username', 'participants__email']
    
    def get_queryset(self):
        """Filter conversations to only show those where user is a participant."""
        user = self.request.user
        return Conversation.objects.filter(
            participants=user
        ).select_related('created_by').prefetch_related(
            'participants', 'messages', 'last_message'
        ).order_by('-last_message_at', '-created_at')
    
    def get_serializer_class(self):
        """Return appropriate serializer based on action."""
        if self.action == 'list':
            return ConversationListSerializer
        return ConversationDetailSerializer
    
    @action(detail=True, methods=['get', 'post'])
    def messages(self, request, pk=None):
        """Get messages in a conversation with pagination and filtering."""
        conversation = self.get_object()
        
        if request.method == 'GET':
            # Get messages with pagination
            page_size = int(request.query_params.get('page_size', 20))
            page = int(request.query_params.get('page', 1))
            
            # Filter messages
            messages = conversation.messages.filter(
                is_deleted=False
            ).select_related('sender').prefetch_related(
                'attachments', 'thread'
            ).order_by('-created_at')
            
            # Pagination
            start = (page - 1) * page_size
            end = start + page_size
            message_slice = messages[start:end]
            
            serializer = MessageListSerializer(message_slice, many=True)
            
            return Response({
                'results': serializer.data,
                'count': messages.count(),
                'page': page,
                'page_size': page_size,
                'conversation_id': conversation.id
            })
        
        elif request.method == 'POST':
            # Send a message in the conversation
            message_data = {
                'conversation': conversation.id,
                'sender': request.user.id,
                'content': request.data.get('content', ''),
                'message_type': request.data.get('message_type', 'text')
            }
            
            # Create message
            serializer = MessageSerializer(data=message_data, context={'request': request})
            if serializer.is_valid(raise_exception=True):
                message = serializer.save()
                
                # Update conversation's last message
                conversation.update_last_message(message)
                
                # Update serializer for response
                message_serializer = MessageSerializer(message, context={'request': request})
                return Response(message_serializer.data, status=status.HTTP_201_CREATED)
    
    @action(detail=True, methods=['post'])
    def add_participant(self, request, pk=None):
        """Add a participant to the conversation."""
        conversation = self.get_object()
        user_id = request.data.get('user_id')
        
        if not user_id:
            raise_validation_error("user_id is required")
        
        try:
            user = User.objects.get(id=user_id)
            conversation.add_participant(user)
            return Response({'status': 'participant_added', 'user_id': user_id})
        except User.DoesNotExist:
            raise_not_found("User not found")
        except ValueError as e:
            raise_validation_error(str(e))
    
    @action(detail=True, methods=['post'])
    def remove_participant(self, request, pk=None):
        """Remove a participant from the conversation."""
        conversation = self.get_object()
        user_id = request.data.get('user_id')
        
        if not user_id:
            raise_validation_error("user_id is required")
        
        try:
            user = User.objects.get(id=user_id)
            conversation.remove_participant(user)
            return Response({'status': 'participant_removed', 'user_id': user_id})
        except User.DoesNotExist:
            raise_not_found("User not found")
        except ValueError as e:
            raise_validation_error(str(e))
    
    @action(detail=True, methods=['post'])
    def mark_as_read(self, request, pk=None):
        """Mark all messages in conversation as read for current user."""
        conversation = self.get_object()
        
        # Get unread messages for this user
        unread_messages = conversation.messages.filter(
            is_read=False
        ).exclude(sender=request.user)
        
        # Mark as read
        count = unread_messages.count()
        unread_messages.update(
            is_read=True,
            read_at=timezone.now()
        )
        
        return Response({
            'status': 'marked_as_read',
            'messages_marked': count
        })
    
    @action(detail=True, methods=['post'])
    def archive(self, request, pk=None):
        """Archive the conversation."""
        conversation = self.get_object()
        conversation.archive_conversation()
        return Response({'status': 'archived'})
    
    @action(detail=True, methods=['post'])
    def leave(self, request, pk=None):
        """Leave the conversation."""
        conversation = self.get_object()
        conversation.remove_participant(request.user)
        return Response({'status': 'left_conversation'})
    
    @action(detail=False, methods=['post'])
    def create_direct(self, request):
        """Create a direct conversation between current user and another user."""
        user_id = request.data.get('user_id')
        
        if not user_id:
            raise_validation_error("user_id is required")
        
        try:
            other_user = User.objects.get(id=user_id)
            conversation = Conversation.objects.get_conversation_between_users(
                request.user, other_user
            )
            
            serializer = ConversationDetailSerializer(conversation, context={'request': request})
            return Response(serializer.data)
        except User.DoesNotExist:
            raise_not_found("User not found")


class MessageViewSet(BaseAPIViewSet):
    """
    ViewSet for message management.
    
    Provides CRUD operations for messages with advanced filtering,
    threading support, and message operations.
    """
    
    serializer_class = MessageSerializer
    queryset = Message.objects.select_related(
        'conversation', 'sender', 'recipient', 'thread'
    ).prefetch_related('attachments')
    
    action_permissions = {
        'list': [CustomIsAuthenticated, IsParticipant],
        'retrieve': [CustomIsAuthenticated, IsParticipant],
        'create': [CustomIsAuthenticated, IsParticipant],
        'update': [CustomIsAuthenticated, CanEditMessage],
        'destroy': [CustomIsAuthenticated, CanDeleteMessage],
        'mark_as_read': [CustomIsAuthenticated, IsParticipant],
        'mark_as_unread': [CustomIsAuthenticated, IsParticipant],
        'edit': [CustomIsAuthenticated, CanEditMessage],
        'delete': [CustomIsAuthenticated, CanDeleteMessage],
        'reply': [CustomIsAuthenticated, IsParticipant],
        'forward': [CustomIsAuthenticated, IsParticipant]
    }
    
    filterset_fields = {
        'conversation': ['exact'],
        'sender': ['exact'],
        'message_type': ['exact'],
        'is_read': ['exact'],
        'is_important': ['exact'],
        'created_at': ['gte', 'lte', 'date'],
        'conversation__conversation_type': ['exact'],
    }
    
    search_fields = ['content', 'sender__username', 'sender__email']
    
    def get_queryset(self):
        """Filter messages to only show those accessible to the user."""
        user = self.request.user
        return Message.objects.filter(
            Q(conversation__participants=user) & Q(is_deleted=False)
        ).select_related(
            'conversation', 'sender', 'recipient', 'thread'
        ).prefetch_related('attachments').order_by('-created_at')
    
    @action(detail=True, methods=['post'])
    def mark_as_read(self, request, pk=None):
        """Mark a specific message as read."""
        message = self.get_object()
        message.mark_as_read()
        
        return Response({
            'status': 'marked_as_read',
            'message_id': message.id,
            'read_at': message.read_at
        })
    
    @action(detail=True, methods=['post'])
    def mark_as_unread(self, request, pk=None):
        """Mark a specific message as unread."""
        message = self.get_object()
        message.is_read = False
        message.read_at = None
        message.save(update_fields=['is_read', 'read_at'])
        
        return Response({
            'status': 'marked_as_unread',
            'message_id': message.id
        })
    
    @action(detail=True, methods=['post'])
    def edit(self, request, pk=None):
        """Edit a message's content."""
        message = self.get_object()
        new_content = request.data.get('content', '').strip()
        
        if not new_content:
            raise_validation_error("Content is required")
        
        message.edit_content(new_content)
        
        serializer = self.get_serializer(message)
        return Response({
            'status': 'edited',
            'message': serializer.data
        })
    
    @action(detail=True, methods=['post'])
    def delete(self, request, pk=None):
        """Soft delete a message."""
        message = self.get_object()
        message.soft_delete(request.user)
        
        return Response({
            'status': 'deleted',
            'message_id': message.id,
            'deleted_at': message.deleted_at
        })
    
    @action(detail=True, methods=['post'])
    def reply(self, request, pk=None):
        """Create a reply to this message."""
        original_message = self.get_object()
        reply_content = request.data.get('content', '').strip()
        
        if not reply_content:
            raise_validation_error("Content is required")
        
        # Create reply
        reply_data = {
            'conversation': original_message.conversation.id,
            'sender': request.user.id,
            'content': reply_content,
            'message_type': 'text',
            'thread': original_message.thread.id if original_message.thread else original_message.id
        }
        
        serializer = MessageSerializer(data=reply_data, context={'request': request})
        if serializer.is_valid(raise_exception=True):
            reply = serializer.save()
            
            # Update conversation's last message
            original_message.conversation.update_last_message(reply)
            
            reply_serializer = MessageSerializer(reply, context={'request': request})
            return Response(reply_serializer.data, status=status.HTTP_201_CREATED)
    
    @action(detail=True, methods=['post'])
    def forward(self, request, pk=None):
        """Forward a message to another conversation."""
        message = self.get_object()
        target_conversation_id = request.data.get('conversation_id')
        
        if not target_conversation_id:
            raise_validation_error("conversation_id is required")
        
        try:
            target_conversation = Conversation.objects.get(
                id=target_conversation_id,
                participants=request.user
            )
            
            # Create forwarded message
            forward_data = {
                'conversation': target_conversation.id,
                'sender': request.user.id,
                'content': f"Forwarded from {message.sender.display_name}:\n\n{message.content}",
                'message_type': 'text'
            }
            
            serializer = MessageSerializer(data=forward_data, context={'request': request})
            if serializer.is_valid(raise_exception=True):
                forwarded_message = serializer.save()
                
                # Update target conversation's last message
                target_conversation.update_last_message(forwarded_message)
                
                forward_serializer = MessageSerializer(forwarded_message, context={'request': request})
                return Response(forward_serializer.data, status=status.HTTP_201_CREATED)
        
        except Conversation.DoesNotExist:
            raise_not_found("Target conversation not found or access denied")
    
    @action(detail=False, methods=['get'])
    def unread(self, request):
        """Get unread messages for the current user."""
        user = request.user
        unread_messages = Message.objects.filter(
            Q(conversation__participants=user) &
            Q(is_read=False) &
            ~Q(sender=user) &
            Q(is_deleted=False)
        ).select_related('conversation', 'sender').order_by('-created_at')
        
        page = self.paginate_queryset(unread_messages)
        if page is not None:
            serializer = MessageListSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = MessageListSerializer(unread_messages, many=True)
        return Response({'results': serializer.data, 'count': unread_messages.count()})


class NotificationViewSet(BaseAPIViewSet):
    """
    ViewSet for notification management.
    
    Provides CRUD operations for notifications with status management
    and filtering capabilities.
    """
    
    serializer_class = NotificationSerializer
    queryset = Notification.objects.select_related('user', 'sender', 'category').order_by('-created_at')
    
    action_permissions = {
        'list': [CustomIsAuthenticated],
        'retrieve': [CustomIsAuthenticated],
        'create': [CustomIsAuthenticated],
        'update': [CustomIsAuthenticated],
        'destroy': [CustomIsAuthenticated],
        'mark_as_read': [CustomIsAuthenticated],
        'mark_as_unread': [CustomIsAuthenticated],
        'mark_all_read': [CustomIsAuthenticated],
        'delete_read': [CustomIsAuthenticated]
    }
    
    filterset_fields = {
        'user': ['exact'],
        'category': ['exact'],
        'priority': ['exact'],
        'status': ['exact'],
        'is_read': ['exact'],
        'is_archived': ['exact'],
        'is_clicked': ['exact'],
        'created_at': ['gte', 'lte', 'date'],
    }
    
    search_fields = ['title', 'message']
    
    def get_queryset(self):
        """Filter notifications to only show those for the current user."""
        user = self.request.user
        return Notification.objects.filter(
            user=user
        ).select_related('sender', 'category').order_by('-created_at')
    
    def get_serializer_class(self):
        """Return appropriate serializer based on action."""
        if self.action == 'list':
            return NotificationListSerializer
        return NotificationSerializer
    
    @action(detail=True, methods=['post'])
    def mark_as_read(self, request, pk=None):
        """Mark a notification as read."""
        notification = self.get_object()
        notification.mark_as_read()
        
        return Response({
            'status': 'marked_as_read',
            'notification_id': notification.id,
            'read_at': notification.read_at
        })
    
    @action(detail=True, methods=['post'])
    def mark_as_unread(self, request, pk=None):
        """Mark a notification as unread."""
        notification = self.get_object()
        notification.is_read = False
        notification.read_at = None
        notification.status = 'pending'
        notification.save(update_fields=['is_read', 'read_at', 'status'])
        
        return Response({
            'status': 'marked_as_unread',
            'notification_id': notification.id
        })
    
    @action(detail=False, methods=['post'])
    def mark_all_read(self, request):
        """Mark all notifications as read for the current user."""
        user = request.user
        
        unread_notifications = self.get_queryset().filter(is_read=False)
        count = unread_notifications.count()
        
        unread_notifications.update(
            is_read=True,
            read_at=timezone.now(),
            status='delivered'
        )
        
        return Response({
            'status': 'all_marked_read',
            'notifications_marked': count
        })
    
    @action(detail=False, methods=['post'])
    def delete_read(self, request):
        """Delete all read notifications for the current user."""
        user = request.user
        
        read_notifications = self.get_queryset().filter(is_read=True)
        count = read_notifications.count()
        
        read_notifications.delete()
        
        return Response({
            'status': 'read_deleted',
            'notifications_deleted': count
        })
    
    @action(detail=False, methods=['get'])
    def unread_count(self, request):
        """Get count of unread notifications."""
        user = request.user
        count = Notification.objects.filter(
            user=user,
            is_read=False
        ).count()
        
        return Response({'unread_count': count})