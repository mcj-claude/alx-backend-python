"""
Custom permission classes for messaging platform API.

Provides granular permission controls for conversations, messages,
and user operations based on roles and participation.
"""

from rest_framework import permissions
from django.shortcuts import get_object_or_404
from .models import Conversation, Message, ConversationParticipant


class IsAuthenticated(permissions.BasePermission):
    """
    Permission that only allows authenticated users to access the view.
    
    This is a custom implementation to ensure all messaging endpoints
    require authentication.
    """
    
    def has_permission(self, request, view):
        """Check if user is authenticated."""
        return bool(request.user and request.user.is_authenticated)


class IsParticipant(permissions.BasePermission):
    """
    Permission that only allows conversation participants to access messages.
    
    Ensures users can only access messages in conversations they are participating in.
    """
    
    def has_object_permission(self, request, view, obj):
        """Check if user is participant in the conversation."""
        if isinstance(obj, Message):
            # For message objects, check conversation participation
            return obj.conversation.is_participant(request.user)
        elif isinstance(obj, Conversation):
            # For conversation objects, check participation
            return obj.is_participant(request.user)
        return False


class IsConversationParticipant(permissions.BasePermission):
    """
    Permission that only allows conversation participants to access conversation endpoints.
    
    Used for conversation-related views that require user to be a participant.
    """
    
    def has_permission(self, request, view):
        """Check if user is authenticated."""
        if not request.user or not request.user.is_authenticated:
            return False
        
        # For conversation-specific views, check conversation access
        if hasattr(view, 'kwargs') and 'conversation_id' in view.kwargs:
            try:
                conversation = Conversation.objects.get(
                    conversation_id=view.kwargs['conversation_id'],
                    is_active=True
                )
                return conversation.is_participant(request.user)
            except Conversation.DoesNotExist:
                return False
        
        return True
    
    def has_object_permission(self, request, view, obj):
        """Check if user is participant in the conversation."""
        return obj.is_participant(request.user)


class IsConversationAdmin(permissions.BasePermission):
    """
    Permission that only allows conversation administrators to modify conversation settings.
    
    Used for actions that require conversation administration privileges.
    """
    
    def has_object_permission(self, request, view, obj):
        """Check if user is conversation administrator."""
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Check if user is participant
        if not obj.is_participant(request.user):
            return False
        
        # Check if user is conversation admin
        participant = obj.conversation_participants.filter(
            user=request.user, is_admin=True
        ).first()
        
        return participant is not None


class IsMessageSender(permissions.BasePermission):
    """
    Permission that only allows message senders to edit their own messages.
    
    Ensures users can only modify messages they sent.
    """
    
    def has_object_permission(self, request, view, obj):
        """Check if user is the sender of the message."""
        if isinstance(obj, Message):
            return obj.sender == request.user
        return False


class CanCreateConversation(permissions.BasePermission):
    """
    Permission that only allows users with sufficient privileges to create conversations.
    
    Based on user roles (host/admin can create, guest cannot).
    """
    
    def has_permission(self, request, view):
        """Check if user can create conversations."""
        if not request.user or not request.user.is_authenticated:
            return False
        
        return request.user.can_create_conversations()


class HasModerationPermissions(permissions.BasePermission):
    """
    Permission that allows users with moderation capabilities to perform admin actions.
    
    Admins and conversation admins can perform moderation actions.
    """
    
    def has_permission(self, request, view):
        """Check if user has moderation permissions."""
        if not request.user or not request.user.is_authenticated:
            return False
        
        return request.user.has_moderation_permissions()
    
    def has_object_permission(self, request, view, obj):
        """Check moderation permissions for specific object."""
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Admins have global moderation permissions
        if request.user.has_moderation_permissions():
            return True
        
        # Check conversation-specific moderation permissions
        if isinstance(obj, Conversation):
            return obj.conversation_participants.filter(
                user=request.user, is_admin=True
            ).exists()
        elif isinstance(obj, Message):
            return obj.conversation.conversation_participants.filter(
                user=request.user, is_admin=True
            ).exists()
        
        return False


class IsOwnerOrReadOnly(permissions.BasePermission):
    """
    Permission that only allows users to edit or delete their own objects.
    
    Generic permission for owner-based operations.
    """
    
    def has_object_permission(self, request, view, obj):
        """Check if user is the owner of the object."""
        if request.method in permissions.SAFE_METHODS:
            return True
        
        # Assume object has 'user', 'sender', or similar owner field
        if hasattr(obj, 'sender'):
            return obj.sender == request.user
        elif hasattr(obj, 'user'):
            return obj.user == request.user
        elif hasattr(obj, 'created_by'):
            return obj.created_by == request.user
        
        return False


class CanViewUserProfile(permissions.BasePermission):
    """
    Permission that controls access to user profile information.
    
    Different rules based on user role and profile visibility settings.
    """
    
    def has_permission(self, request, view):
        """Check if user can view profiles."""
        if not request.user or not request.user.is_authenticated:
            return False
        
        return True
    
    def has_object_permission(self, request, view, obj):
        """Check if user can view specific profile."""
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Users can always view their own profile
        if obj == request.user:
            return True
        
        # Admins can view all profiles
        if request.user.has_moderation_permissions():
            return True
        
        # Check if profile is public
        if hasattr(obj, 'is_profile_public') and obj.is_profile_public:
            return True
        
        return False


class RateLimitPermission(permissions.BasePermission):
    """
    Permission that checks rate limiting for API endpoints.
    
    Can be used to implement custom rate limiting logic.
    """
    
    def has_permission(self, request, view):
        """Check rate limiting for the current user."""
        if not request.user or not request.user.is_authenticated:
            return True  # Allow anonymous requests to be rate-limited by other means
        
        # Check if user is rate limited
        # This could integrate with Django rate limiting backends
        # For now, just allow all authenticated users
        return True
    
    def has_object_permission(self, request, view, obj):
        """Check rate limiting for specific objects."""
        return True  # Apply same logic to object-level permissions


class SafeMethodsPermission(permissions.BasePermission):
    """
    Permission that only allows safe HTTP methods for unauthenticated users.
    
    Allows GET, HEAD, OPTIONS requests for anonymous users.
    """
    
    def has_permission(self, request, view):
        """Check permission based on HTTP method and authentication."""
        if request.method in permissions.SAFE_METHODS:
            return True
        
        return bool(request.user and request.user.is_authenticated)


# Permission combinations for common use cases

class ConversationPermissions:
    """
    Permission class that combines multiple conversation-related permissions.
    
    Provides comprehensive permission checking for conversation operations.
    """
    
    @staticmethod
    def can_view_conversation(user, conversation):
        """Check if user can view a conversation."""
        if not user or not user.is_authenticated:
            return False
        return conversation.is_participant(user)
    
    @staticmethod
    def can_send_message(user, conversation):
        """Check if user can send messages to a conversation."""
        if not ConversationPermissions.can_view_conversation(user, conversation):
            return False
        
        # Check if conversation allows messaging
        if hasattr(conversation, 'is_active') and not conversation.is_active:
            return False
        
        return True
    
    @staticmethod
    def can_manage_participants(user, conversation):
        """Check if user can manage conversation participants."""
        if not ConversationPermissions.can_view_conversation(user, conversation):
            return False
        
        # Check conversation admin privileges
        participant = conversation.conversation_participants.filter(
            user=user, is_admin=True
        ).first()
        
        return participant is not None
    
    @staticmethod
    def can_delete_conversation(user, conversation):
        """Check if user can delete a conversation."""
        if not ConversationPermissions.can_view_conversation(user, conversation):
            return False
        
        # Creator or admins can delete
        return (
            conversation.created_by == user or
            conversation.created_by == user or
            user.has_moderation_permissions()
        )


class MessagePermissions:
    """
    Permission class that provides message-specific permission checks.
    """
    
    @staticmethod
    def can_view_message(user, message):
        """Check if user can view a specific message."""
        return ConversationPermissions.can_view_conversation(user, message.conversation)
    
    @staticmethod
    def can_edit_message(user, message):
        """Check if user can edit a specific message."""
        if not MessagePermissions.can_view_message(user, message):
            return False
        
        # Sender can edit their own messages
        return message.sender == user
    
    @staticmethod
    def can_delete_message(user, message):
        """Check if user can delete a specific message."""
        if not MessagePermissions.can_view_message(user, message):
            return False
        
        # Sender, conversation admins, or global admins can delete
        return (
            message.sender == user or
            ConversationPermissions.can_manage_participants(user, message.conversation) or
            user.has_moderation_permissions()
        )
    
    @staticmethod
    def can_reply_to_message(user, message):
        """Check if user can reply to a specific message."""
        return MessagePermissions.can_view_message(user, message)


class UserPermissions:
    """
    Permission class that provides user-related permission checks.
    """
    
    @staticmethod
    def can_view_user_profile(viewer, target_user):
        """Check if viewer can view target user's profile."""
        if not viewer or not viewer.is_authenticated:
            return False
        
        # Users can view their own profile
        if viewer == target_user:
            return True
        
        # Admins can view all profiles
        if viewer.has_moderation_permissions():
            return True
        
        # Check if target user's profile is public
        if hasattr(target_user, 'is_profile_public') and target_user.is_profile_public:
            return True
        
        return False
    
    @staticmethod
    def can_add_to_conversation(inviter, target_user, conversation):
        """Check if inviter can add target_user to conversation."""
        if not ConversationPermissions.can_manage_participants(inviter, conversation):
            return False
        
        # Cannot add users who are already participants
        if conversation.is_participant(target_user):
            return False
        
        # Check if target user can be added (e.g., guest users)
        if hasattr(target_user, 'can_create_conversations') and not target_user.can_create_conversations():
            # Allow adding guests, but may have different permissions in conversation
            pass
        
        return True