"""
Custom permission classes and authentication backends for the messaging platform API.

Provides fine-grained control over API access and user permissions.
"""

from rest_framework import permissions
from rest_framework.exceptions import PermissionDenied
from django.contrib.auth.models import AnonymousUser
from .exceptions import raise_permission_error, raise_authentication_error


class BaseSafePermission(permissions.BasePermission):
    """
    Base permission class with common functionality for safe permissions.
    
    Provides common methods for permission checking and audit logging.
    """
    
    def has_permission(self, request, view):
        """Override in subclasses to implement permission logic."""
        return True
    
    def has_object_permission(self, request, view, obj):
        """Override in subclasses to implement object-level permission logic."""
        return True
    
    def check_permission(self, request, message=None):
        """Check basic permission and raise exception if not satisfied."""
        if not self.has_permission(request, None):
            raise_permission_error(message or "Permission denied")
    
    def check_object_permission(self, request, obj, message=None):
        """Check object-level permission and raise exception if not satisfied."""
        if not self.has_object_permission(request, None, obj):
            raise_permission_error(message or "Object permission denied")
    
    def is_authenticated_user(self, request):
        """Check if user is authenticated."""
        return request.user and isinstance(request.user, AnonymousUser) is False and request.user.is_authenticated
    
    def is_staff_user(self, request):
        """Check if user is staff."""
        return self.is_authenticated_user(request) and request.user.is_staff
    
    def is_superuser(self, request):
        """Check if user is superuser."""
        return self.is_authenticated_user(request) and request.user.is_superuser


class IsAuthenticated(BaseSafePermission):
    """
    Permission that only allows access to authenticated users.
    
    This is the most basic permission - just requires authentication.
    """
    
    def has_permission(self, request, view):
        if not self.is_authenticated_user(request):
            raise_authentication_error("Authentication is required to access this resource")
        return True


class IsOwnerOrReadOnly(BaseSafePermission):
    """
    Permission that allows read access to all users, but write access only to owners.
    
    Used for resources where users should only be able to modify their own data.
    """
    
    def has_object_permission(self, request, view, obj):
        # Read permissions for any request
        if request.method in permissions.SAFE_METHODS:
            return True
        
        # Write permissions only to the owner
        return getattr(obj, 'user', None) == request.user


class IsOwner(BaseSafePermission):
    """
    Permission that only allows access to the owner of the resource.
    
    More restrictive than IsOwnerOrReadOnly - no read access for non-owners.
    """
    
    def has_object_permission(self, request, view, obj):
        return getattr(obj, 'user', None) == request.user


class IsParticipant(BaseSafePermission):
    """
    Permission for conversation-related resources.
    
    Allows access only to users who are participants in the conversation.
    """
    
    def has_object_permission(self, request, view, obj):
        if hasattr(obj, 'participants'):
            return request.user in obj.participants.all()
        elif hasattr(obj, 'conversation'):
            return request.user in obj.conversation.participants.all()
        return False


class IsConversationParticipant(IsParticipant):
    """
    Specific permission for conversation access.
    
    Checks if user is a participant in the conversation.
    """
    
    def has_object_permission(self, request, view, obj):
        return self.has_object_permission(request, view, obj)


class IsMessageSender(BaseSafePermission):
    """
    Permission for message-related operations.
    
    Allows access only to the sender of the message.
    """
    
    def has_object_permission(self, request, view, obj):
        return getattr(obj, 'sender', None) == request.user


class IsMessageRecipient(BaseSafePermission):
    """
    Permission for message recipient operations.
    
    Allows access to recipients of direct messages.
    """
    
    def has_object_permission(self, request, view, obj):
        if hasattr(obj, 'recipient') and obj.recipient:
            return obj.recipient == request.user
        return False


class IsAdminUser(BaseSafePermission):
    """
    Permission that only allows access to admin users.
    
    Used for administrative operations and sensitive data access.
    """
    
    def has_permission(self, request, view):
        if not self.is_staff_user(request):
            raise_permission_error("Admin access required")
        return True


class IsStaffOrReadOnly(BaseSafePermission):
    """
    Permission that allows read access to all users, write access only to staff.
    """
    
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        return self.is_staff_user(request)


class IsVerifiedUser(BaseSafePermission):
    """
    Permission that only allows access to verified users.
    
    Ensures only users with verified accounts can access certain features.
    """
    
    def has_permission(self, request, view):
        if not self.is_authenticated_user(request):
            raise_authentication_error("Authentication required")
        
        if not getattr(request.user, 'is_verified', False):
            raise_permission_error("Account verification required")
        
        return True


class IsActiveUser(BaseSafePermission):
    """
    Permission that only allows access to active users.
    
    Blocks access from suspended or disabled accounts.
    """
    
    def has_permission(self, request, view):
        if not self.is_authenticated_user(request):
            raise_authentication_error("Authentication required")
        
        if not getattr(request.user, 'is_active', False):
            raise_permission_error("Account is inactive")
        
        if getattr(request.user, 'is_suspended', False):
            raise_permission_error("Account is suspended")
        
        return True


class CanManageConversation(BaseSafePermission):
    """
    Permission for conversation management operations.
    
    Allows conversation creators and admins to manage conversations.
    """
    
    def has_object_permission(self, request, view, obj):
        # Allow if user is the creator
        if getattr(obj, 'created_by', None) == request.user:
            return True
        
        # Allow if user is staff
        if self.is_staff_user(request):
            return True
        
        # Allow if user has explicit permission (can be extended)
        return self._has_conversation_permission(request.user, obj)
    
    def _has_conversation_permission(self, user, conversation):
        """Check if user has conversation management permission."""
        # This can be extended to check user roles or permissions
        return user in conversation.participants.all()


class CanEditMessage(BaseSafePermission):
    """
    Permission for message editing operations.
    
    Allows message editing under specific conditions.
    """
    
    def has_object_permission(self, request, view, obj):
        # Allow if user is the sender
        if getattr(obj, 'sender', None) == request.user:
            # Check if message is within edit time limit (e.g., 5 minutes)
            if hasattr(obj, 'created_at'):
                from django.utils import timezone
                time_diff = timezone.now() - obj.created_at
                if time_diff.total_seconds() < 300:  # 5 minutes
                    return True
            return True
        
        # Allow if user is staff
        if self.is_staff_user(request):
            return True
        
        return False


class CanDeleteMessage(BaseSafePermission):
    """
    Permission for message deletion operations.
    
    Controls who can delete messages and under what conditions.
    """
    
    def has_object_permission(self, request, view, obj):
        # Allow if user is the sender (with time limit)
        if getattr(obj, 'sender', None) == request.user:
            if hasattr(obj, 'created_at'):
                from django.utils import timezone
                time_diff = timezone.now() - obj.created_at
                if time_diff.total_seconds() < 3600:  # 1 hour
                    return True
            return True
        
        # Allow if user is conversation creator
        if hasattr(obj, 'conversation'):
            if getattr(obj.conversation, 'created_by', None) == request.user:
                return True
        
        # Allow if user is staff
        if self.is_staff_user(request):
            return True
        
        return False


class RateLimitPermission(BaseSafePermission):
    """
    Permission that implements rate limiting for API endpoints.
    
    Prevents abuse by limiting request frequency.
    """
    
    def __init__(self, limit=100, window=60):
        """
        Initialize rate limit permission.
        
        Args:
            limit (int): Maximum number of requests allowed
            window (int): Time window in seconds
        """
        self.limit = limit
        self.window = window
    
    def has_permission(self, request, view):
        if not self.is_authenticated_user(request):
            return True  # Don't rate limit anonymous users
        
        from django.core.cache import cache
        import time
        
        # Create a unique key for this user and endpoint
        key = f"rate_limit:{request.user.id}:{request.path}"
        
        # Get current request count
        current_requests = cache.get(key, 0)
        
        # Check if limit exceeded
        if current_requests >= self.limit:
            from .exceptions import raise_rate_limit_error
            raise_rate_limit_error(f"Rate limit exceeded. Maximum {self.limit} requests per {self.window} seconds")
        
        # Increment counter
        cache.set(key, current_requests + 1, self.window)
        
        return True


class SSLRequired(BaseSafePermission):
    """
    Permission that requires SSL/HTTPS for write operations.
    
    Ensures sensitive operations are performed over secure connections.
    """
    
    def has_permission(self, request, view):
        if request.method in ['POST', 'PUT', 'PATCH', 'DELETE']:
            if not request.is_secure():
                raise_permission_error("SSL/HTTPS required for this operation")
        return True


class CustomModelPermission(BaseSafePermission):
    """
    Permission that uses Django's model-level permissions.
    
    Checks if user has the required model permissions.
    """
    
    def __init__(self, model_name, action):
        """
        Initialize model permission.
        
        Args:
            model_name (str): Name of the model
            action (str): Permission action (view, add, change, delete)
        """
        self.model_name = model_name
        self.action = action
    
    def has_permission(self, request, view):
        if not self.is_authenticated_user(request):
            raise_authentication_error("Authentication required")
        
        permission_name = f"{self.model_name}_{self.action}"
        if not request.user.has_perm(f"messaging.{permission_name}"):
            raise_permission_error(f"Missing permission: {permission_name}")
        
        return True


# Permission combinations for common use cases
class ReadOnly(BaseSafePermission):
    """Permission that only allows read operations."""
    
    def has_permission(self, request, view):
        return request.method in permissions.SAFE_METHODS


class AuthenticatedReadOnly(BaseSafePermission):
    """Permission that allows read operations for authenticated users only."""
    
    def has_permission(self, request, view):
        return self.is_authenticated_user(request) and request.method in permissions.SAFE_METHODS


class StaffOrOwner(BaseSafePermission):
    """Permission that allows access to staff or resource owners."""
    
    def has_permission(self, request, view):
        return self.is_staff_user(request)
    
    def has_object_permission(self, request, view, obj):
        return self.is_staff_user(request) or getattr(obj, 'user', None) == request.user


class AdminOrCreator(BaseSafePermission):
    """Permission that allows access to admin users or resource creators."""
    
    def has_permission(self, request, view):
        return self.is_staff_user(request)
    
    def has_object_permission(self, request, view, obj):
        return (self.is_staff_user(request) or 
                getattr(obj, 'created_by', None) == request.user or
                getattr(obj, 'user', None) == request.user)


# Composition permissions for complex scenarios
class AndPermission(BaseSafePermission):
    """Composition permission that requires all given permissions to be satisfied."""
    
    def __init__(self, *permissions):
        self.permissions = permissions
    
    def has_permission(self, request, view):
        return all(perm.has_permission(request, view) for perm in self.permissions)
    
    def has_object_permission(self, request, view, obj):
        return all(perm.has_object_permission(request, view, obj) for perm in self.permissions)


class OrPermission(BaseSafePermission):
    """Composition permission that requires at least one of the given permissions to be satisfied."""
    
    def __init__(self, *permissions):
        self.permissions = permissions
    
    def has_permission(self, request, view):
        return any(perm.has_permission(request, view) for perm in self.permissions)
    
    def has_object_permission(self, request, view, obj):
        return any(perm.has_object_permission(request, view, obj) for perm in self.permissions)