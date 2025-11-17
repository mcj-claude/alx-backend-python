"""
Django REST Framework viewsets for messaging platform API.

Provides comprehensive API endpoints for conversations and messages with
proper authentication, validation, and error handling.
"""

from rest_framework import viewsets, status, generics
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework import filters
from django.db.models import Q, Count, Max
from django.shortcuts import get_object_or_404
from django.core.exceptions import ValidationError
from django.utils import timezone

from .models import User, Conversation, Message, ConversationParticipant, UserRole
from .serializers import (
    UserSerializer, ConversationSerializer, MessageSerializer,
    ConversationListSerializer, MessageListSerializer
)
from .permissions import IsParticipant, IsConversationParticipant


class UserViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Read-only viewset for user information.
    
    Provides endpoint for retrieving user profile information
    for authenticated users.
    """
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """Return users based on search and role filtering."""
        queryset = User.objects.filter(is_active=True)
        
        # Search functionality
        search = self.request.query_params.get('search', None)
        if search:
            queryset = queryset.filter(
                Q(email__icontains=search) |
                Q(first_name__icontains=search) |
                Q(last_name__icontains=search)
            )
        
        # Role filtering
        role = self.request.query_params.get('role', None)
        if role and role in UserRole.values:
            queryset = queryset.filter(role=role)
        
        return queryset.select_related()
    
    @action(detail=False, methods=['get'])
    def me(self, request):
        """Get current authenticated user's profile."""
        serializer = self.get_serializer(request.user)
        return Response(serializer.data, status=status.HTTP_200_OK)


class ConversationViewSet(viewsets.GenericViewSet):
    """
    Viewset for conversation management with custom endpoints.
    
    Supports listing, creating, and retrieving conversations
    with participant management.
    """
    serializer_class = ConversationSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = 'conversation_id'
    
    def get_queryset(self):
        """Return conversations for authenticated user."""
        return Conversation.objects.filter(
            participants=self.request.user,
            is_active=True
        ).select_related().prefetch_related('participants').annotate(
            message_count=Count('messages', filter=Q(messages__is_deleted=False))
        )
    
    def list(self, request):
        """
        GET /conversations/
        
        List all conversations for the authenticated user
        with participant info and message counts.
        """
        conversations = self.get_queryset()
        
        # Serialization with conversation list serializer
        serializer = ConversationListSerializer(conversations, many=True, context={'request': request})
        
        # Pagination
        page = self.paginate_queryset(conversations)
        if page is not None:
            serializer = ConversationListSerializer(page, many=True, context={'request': request})
            return self.get_paginated_response(serializer.data)
        
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    def create(self, request):
        """
        POST /conversations/
        
        Create a new conversation with participants.
        """
        data = request.data.copy()
        data['created_by'] = request.user.id
        
        serializer = self.get_serializer(data=data, context={'request': request})
        
        if serializer.is_valid():
            # Check if user can create conversations
            if not request.user.can_create_conversations():
                return Response(
                    {'detail': 'Insufficient permissions to create conversations.'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            conversation = serializer.save()
            
            # Add creator as participant with admin privileges
            conversation.add_participant(request.user, is_admin=True)
            
            # Add additional participants if specified
            participant_ids = request.data.get('participant_ids', [])
            for participant_id in participant_ids:
                try:
                    participant = User.objects.get(id=participant_id)
                    conversation.add_participant(participant)
                except User.DoesNotExist:
                    continue
            
            # Return created conversation
            response_serializer = ConversationSerializer(conversation, context={'request': request})
            return Response(response_serializer.data, status=status.HTTP_201_CREATED)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    def retrieve(self, request, conversation_id=None):
        """
        GET /conversations/{id}/
        
        Retrieve conversation details with participant info and message count.
        """
        conversation = get_object_or_404(
            Conversation.objects.select_related().prefetch_related('participants'),
            conversation_id=conversation_id,
            is_active=True
        )
        
        # Check if user is participant
        if not conversation.is_participant(request.user):
            return Response(
                {'detail': 'You are not authorized to access this conversation.'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        serializer = self.get_serializer(conversation, context={'request': request})
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    @action(detail=True, methods=['post'])
    def add_participant(self, request, conversation_id=None):
        """
        POST /conversations/{id}/add_participant/
        
        Add a participant to the conversation (conversation admins only).
        """
        conversation = get_object_or_404(
            Conversation.objects.prefetch_related('participants'),
            conversation_id=conversation_id
        )
        
        # Check if user is conversation admin
        if not conversation.is_participant(request.user):
            return Response(
                {'detail': 'You are not authorized to modify this conversation.'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Check admin privileges
        participant = conversation.conversation_participants.filter(
            user=request.user, is_admin=True
        ).first()
        
        if not participant:
            return Response(
                {'detail': 'Only conversation administrators can add participants.'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Get user to add
        user_id = request.data.get('user_id')
        if not user_id:
            return Response(
                {'detail': 'user_id is required.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            user_to_add = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response(
                {'detail': 'User not found.'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Check if user is already a participant
        if conversation.is_participant(user_to_add):
            return Response(
                {'detail': 'User is already a participant in this conversation.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Add participant
        try:
            conversation.add_participant(user_to_add)
            return Response(
                {'detail': 'Participant added successfully.'},
                status=status.HTTP_200_OK
            )
        except ValidationError as e:
            return Response(
                {'detail': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['post'])
    def remove_participant(self, request, conversation_id=None):
        """
        POST /conversations/{id}/remove_participant/
        
        Remove a participant from the conversation (conversation admins only).
        """
        conversation = get_object_or_404(
            Conversation.objects.prefetch_related('participants'),
            conversation_id=conversation_id
        )
        
        # Check if user is conversation admin
        participant = conversation.conversation_participants.filter(
            user=request.user, is_admin=True
        ).first()
        
        if not participant:
            return Response(
                {'detail': 'Only conversation administrators can remove participants.'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Get user to remove
        user_id = request.data.get('user_id')
        if not user_id:
            return Response(
                {'detail': 'user_id is required.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            user_to_remove = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response(
                {'detail': 'User not found.'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Check if user is participant
        if not conversation.is_participant(user_to_remove):
            return Response(
                {'detail': 'User is not a participant in this conversation.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Remove participant
        try:
            conversation.remove_participant(user_to_remove)
            return Response(
                {'detail': 'Participant removed successfully.'},
                status=status.HTTP_200_OK
            )
        except ValidationError as e:
            return Response(
                {'detail': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['get'])
    def list_messages(self, request, conversation_id=None):
        """
        GET /conversations/{id}/messages/
        
        List messages for the conversation ordered chronologically.
        """
        conversation = get_object_or_404(
            Conversation.objects.prefetch_related('participants'),
            conversation_id=conversation_id,
            is_active=True
        )
        
        # Check if user is participant
        if not conversation.is_participant(request.user):
            return Response(
                {'detail': 'You are not authorized to access this conversation.'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Get messages with pagination
        messages = conversation.messages.filter(is_deleted=False).order_by('sent_at')
        
        # Pagination
        page = self.paginate_queryset(messages)
        if page is not None:
            serializer = MessageListSerializer(page, many=True, context={'request': request})
            return self.get_paginated_response(serializer.data)
        
        serializer = MessageListSerializer(messages, many=True, context={'request': request})
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    @action(detail=True, methods=['post'])
    def send_message(self, request, conversation_id=None):
        """
        POST /conversations/{id}/messages/
        
        Send a new message to the conversation.
        """
        conversation = get_object_or_404(
            Conversation.objects.prefetch_related('participants'),
            conversation_id=conversation_id,
            is_active=True
        )
        
        # Check if user is participant
        if not conversation.is_participant(request.user):
            return Response(
                {'detail': 'You are not authorized to send messages to this conversation.'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Validate message data
        data = {
            'sender': request.user.id,
            'conversation': conversation.id,
            'message_body': request.data.get('message_body', '').strip()
        }
        
        # Check if replying to another message
        if 'reply_to' in request.data:
            reply_to_id = request.data.get('reply_to')
            try:
                reply_message = Message.objects.get(
                    message_id=reply_to_id,
                    conversation=conversation,
                    is_deleted=False
                )
                data['reply_to'] = reply_message.id
            except Message.DoesNotExist:
                return Response(
                    {'detail': 'Reply message not found.'},
                    status=status.HTTP_404_NOT_FOUND
                )
        
        serializer = MessageSerializer(data=data, context={'request': request})
        
        if serializer.is_valid():
            message = serializer.save()
            
            # Update conversation's message count
            conversation.message_count = conversation.get_message_count()
            conversation.save(update_fields=['message_count'])
            
            # Return created message
            response_serializer = MessageSerializer(message, context={'request': request})
            return Response(response_serializer.data, status=status.HTTP_201_CREATED)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class MessageViewSet(viewsets.GenericViewSet):
    """
    Viewset for individual message operations.
    
    Provides endpoints for retrieving, updating, and deleting messages.
    """
    serializer_class = MessageSerializer
    permission_classes = [IsAuthenticated, IsParticipant]
    lookup_field = 'message_id'
    
    def get_queryset(self):
        """Return messages for authenticated user."""
        return Message.objects.filter(
            conversation__participants=self.request.user,
            is_deleted=False
        ).select_related('sender', 'conversation')
    
    def retrieve(self, request, message_id=None):
        """
        GET /messages/{id}/
        
        Retrieve individual message details.
        """
        message = get_object_or_404(
            self.get_queryset(),
            message_id=message_id
        )
        
        serializer = self.get_serializer(message, context={'request': request})
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    def update(self, request, message_id=None):
        """
        PUT/PATCH /messages/{id}/
        
        Update message content (only sender can edit).
        """
        message = get_object_or_404(
            self.get_queryset(),
            message_id=message_id
        )
        
        # Check if user is sender
        if message.sender != request.user:
            return Response(
                {'detail': 'You can only edit your own messages.'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Only allow editing message body
        data = {
            'message_body': request.data.get('message_body', message.message_body).strip()
        }
        
        serializer = self.get_serializer(message, data=data, partial=True, context={'request': request})
        
        if serializer.is_valid():
            updated_message = serializer.save()
            
            response_serializer = MessageSerializer(updated_message, context={'request': request})
            return Response(response_serializer.data, status=status.HTTP_200_OK)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    def destroy(self, request, message_id=None):
        """
        DELETE /messages/{id}/
        
        Soft delete message (only sender or conversation admin can delete).
        """
        message = get_object_or_404(
            self.get_queryset(),
            message_id=message_id
        )
        
        # Check permissions: sender or conversation admin
        can_delete = (
            message.sender == request.user or
            message.conversation.get_admin_participants().filter(id=request.user.id).exists() or
            request.user.has_moderation_permissions()
        )
        
        if not can_delete:
            return Response(
                {'detail': 'You do not have permission to delete this message.'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Soft delete
        message.soft_delete()
        
        return Response(
            {'detail': 'Message deleted successfully.'},
            status=status.HTTP_200_OK
        )
    
    @action(detail=True, methods=['post'])
    def mark_read(self, request, message_id=None):
        """
        POST /messages/{id}/mark_read/
        
        Mark message as read.
        """
        message = get_object_or_404(
            self.get_queryset(),
            message_id=message_id
        )
        
        # Check if user is participant in conversation
        if not message.conversation.is_participant(request.user):
            return Response(
                {'detail': 'You are not authorized to mark messages as read in this conversation.'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Mark as read
        message.mark_as_read(request.user)
        
        return Response(
            {'detail': 'Message marked as read.'},
            status=status.HTTP_200_OK
        )


class ConversationMessagesViewSet(viewsets.GenericViewSet):
    """
    Nested viewset for messages within a conversation.
    
    Provides direct endpoints for conversation messages.
    """
    serializer_class = MessageListSerializer
    permission_classes = [IsAuthenticated, IsParticipant]
    
    def get_conversation(self):
        """Get conversation from URL parameter."""
        conversation_id = self.kwargs.get('conversation_id')
        return get_object_or_404(
            Conversation.objects.prefetch_related('participants'),
            conversation_id=conversation_id,
            is_active=True
        )
    
    def check_conversation_access(self, conversation):
        """Check if user has access to the conversation."""
        if not conversation.is_participant(self.request.user):
            return Response(
                {'detail': 'You are not authorized to access this conversation.'},
                status=status.HTTP_403_FORBIDDEN
            )
        return None
    
    def list(self, request, conversation_id=None):
        """
        GET /conversations/{conversation_id}/messages/
        
        List messages for the conversation ordered chronologically.
        """
        conversation = self.get_conversation()
        
        # Check access
        access_error = self.check_conversation_access(conversation)
        if access_error:
            return access_error
        
        # Get messages
        messages = conversation.messages.filter(is_deleted=False).order_by('sent_at')
        
        # Pagination
        page = self.paginate_queryset(messages)
        if page is not None:
            serializer = MessageListSerializer(page, many=True, context={'request': request})
            return self.get_paginated_response(serializer.data)
        
        serializer = MessageListSerializer(messages, many=True, context={'request': request})
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    def create(self, request, conversation_id=None):
        """
        POST /conversations/{conversation_id}/messages/
        
        Send a new message to the conversation.
        """
        conversation = self.get_conversation()
        
        # Check access
        access_error = self.check_conversation_access(conversation)
        if access_error:
            return access_error
        
        # Validate message data
        data = {
            'sender': request.user.id,
            'conversation': conversation.id,
            'message_body': request.data.get('message_body', '').strip()
        }
        
        # Check if replying to another message
        if 'reply_to' in request.data:
            reply_to_id = request.data.get('reply_to')
            try:
                reply_message = Message.objects.get(
                    message_id=reply_to_id,
                    conversation=conversation,
                    is_deleted=False
                )
                data['reply_to'] = reply_message.id
            except Message.DoesNotExist:
                return Response(
                    {'detail': 'Reply message not found.'},
                    status=status.HTTP_404_NOT_FOUND
                )
        
        serializer = MessageSerializer(data=data, context={'request': request})
        
        if serializer.is_valid():
            message = serializer.save()
            
            # Update conversation's message count
            conversation.message_count = conversation.get_message_count()
            conversation.save(update_fields=['message_count'])
            
            # Return created message
            response_serializer = MessageSerializer(message, context={'request': request})
            return Response(response_serializer.data, status=status.HTTP_201_CREATED)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)