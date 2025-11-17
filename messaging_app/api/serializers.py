"""
Custom serializers for the messaging platform API.

Provides advanced serialization features including nested serialization,
dynamic field selection, and custom validation logic.
"""

from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.core.exceptions import ValidationError
import logging

from ..exceptions import validate_required_fields, validate_email_format, validate_content_length
from ..models import (
    User, Conversation, Message, MessageThread, MessageAttachment,
    Notification, NotificationChannel, NotificationCategory
)

logger = logging.getLogger(__name__)
UserModel = get_user_model()


class DynamicFieldsModelSerializer(serializers.ModelSerializer):
    """
    Base serializer that supports dynamic field inclusion/exclusion.
    
    Allows clients to specify which fields they want via the `fields` query parameter.
    """
    
    def __init__(self, *args, **kwargs):
        # Don't pass 'fields' arg up to the superclass
        fields = kwargs.pop('fields', None)
        
        # Instantiate the superclass normally
        super().__init__(*args, **kwargs)
        
        if fields is not None:
            # Drop any fields that are not specified in the `fields` argument
            allowed = set(fields)
            existing = set(self.fields.keys())
            for field_name in existing - allowed:
                self.fields.pop(field_name)


class NestedSerializerMixin:
    """
    Mixin for handling nested serializers with proper validation.
    
    Provides methods to handle nested relationships and validate complex data.
    """
    
    def validate_nested_data(self, data, field_name, serializer_class):
        """Validate nested data using the specified serializer."""
        if field_name not in data:
            return None
        
        nested_data = data[field_name]
        if nested_data is None:
            return None
        
        try:
            nested_serializer = serializer_class(data=nested_data)
            if nested_serializer.is_valid(raise_exception=True):
                return nested_serializer.validated_data
            else:
                raise serializers.ValidationError(nested_serializer.errors)
        except Exception as e:
            logger.error(f"Error validating nested data for {field_name}: {e}")
            raise serializers.ValidationError({field_name: "Invalid nested data"})
    
    def create_nested_object(self, data, field_name, serializer_class, **kwargs):
        """Create a nested object using the specified serializer."""
        nested_data = data.get(field_name)
        if nested_data is None:
            return None
        
        nested_data.update(kwargs)
        nested_serializer = serializer_class(data=nested_data)
        
        if nested_serializer.is_valid(raise_exception=True):
            return nested_serializer.save()
        else:
            raise serializers.ValidationError({field_name: nested_serializer.errors})


class TimestampMixin:
    """
    Mixin for handling timestamp fields consistently.
    
    Provides methods for managing created_at, updated_at, and other timestamp fields.
    """
    
    def get_timestamp(self, obj, field_name='created_at'):
        """Get timestamp in ISO format."""
        timestamp = getattr(obj, field_name, None)
        return timestamp.isoformat() if timestamp else None
    
    def validate_timestamp(self, value, field_name):
        """Validate timestamp format."""
        if value and isinstance(value, str):
            try:
                # Attempt to parse ISO format
                from dateutil import parser
                parsed = parser.parse(value)
                return parsed
            except Exception:
                raise serializers.ValidationError(f"Invalid {field_name} format. Use ISO format.")
        return value


class UserProfileSerializer(DynamicFieldsModelSerializer, TimestampMixin, NestedSerializerMixin):
    """
    Serializer for user profile data.
    
    Handles user information, profile settings, and activity data.
    """
    
    full_name = serializers.CharField(source='get_full_name', read_only=True)
    display_name = serializers.CharField(source='display_name', read_only=True)
    is_online = serializers.BooleanField(source='is_online', read_only=True)
    unread_notifications_count = serializers.IntegerField(source='get_unread_notifications_count', read_only=True)
    unread_messages_count = serializers.IntegerField(source='get_unread_messages_count', read_only=True)
    
    # Password field for creation/update (write-only)
    password = serializers.CharField(write_only=True, required=False, min_length=8)
    
    # Timestamps
    created_at_formatted = serializers.SerializerMethodField()
    last_seen_formatted = serializers.SerializerMethodField()
    
    class Meta:
        model = UserModel
        fields = [
            'id', 'email', 'username', 'first_name', 'last_name', 'full_name', 'display_name',
            'phone_number', 'profile_picture', 'bio', 'date_of_birth', 'is_verified',
            'is_online', 'is_active', 'last_seen', 'last_seen_formatted',
            'preferred_language', 'timezone', 'email_notifications', 'push_notifications',
            'two_factor_enabled', 'show_online_status', 'is_profile_public', 'is_phone_visible',
            'unread_notifications_count', 'unread_messages_count', 'created_at', 'created_at_formatted',
            'updated_at', 'password'
        ]
        read_only_fields = [
            'id', 'is_online', 'unread_notifications_count', 'unread_messages_count',
            'last_seen', 'created_at', 'updated_at', 'two_factor_enabled'
        ]
    
    def get_created_at_formatted(self, obj):
        return self.get_timestamp(obj, 'created_at')
    
    def get_last_seen_formatted(self, obj):
        return self.get_timestamp(obj, 'last_seen')
    
    def validate_email(self, value):
        """Validate email format and uniqueness."""
        if value:
            validate_email_format(value)
            
            # Check uniqueness (excluding current user if updating)
            queryset = UserModel.objects.filter(email=value)
            if hasattr(self.instance, 'id'):
                queryset = queryset.exclude(id=self.instance.id)
            
            if queryset.exists():
                raise serializers.ValidationError("A user with this email already exists.")
        return value
    
    def validate_username(self, value):
        """Validate username format and uniqueness."""
        if value:
            if len(value) < 3:
                raise serializers.ValidationError("Username must be at least 3 characters long.")
            
            if not value.replace('_', '').replace('-', '').isalnum():
                raise serializers.ValidationError("Username can only contain letters, numbers, hyphens, and underscores.")
            
            # Check uniqueness (excluding current user if updating)
            queryset = UserModel.objects.filter(username=value)
            if hasattr(self.instance, 'id'):
                queryset = queryset.exclude(id=self.instance.id)
            
            if queryset.exists():
                raise serializers.ValidationError("A user with this username already exists.")
        return value
    
    def validate_password(self, value):
        """Validate password strength."""
        if value:
            if len(value) < 8:
                raise serializers.ValidationError("Password must be at least 8 characters long.")
            
            if value.isdigit() or value.isalpha():
                raise serializers.ValidationError("Password must contain both letters and numbers.")
        return value
    
    def validate_phone_number(self, value):
        """Validate phone number format."""
        if value:
            validate_phone_format(value)
        return value
    
    def create(self, validated_data):
        """Create a new user with hashed password."""
        password = validated_data.pop('password', None)
        user = super().create(validated_data)
        
        if password:
            user.set_password(password)
            user.save()
        
        logger.info(f"User created: {user.email}")
        return user
    
    def update(self, instance, validated_data):
        """Update user, handling password separately."""
        password = validated_data.pop('password', None)
        
        if password:
            instance.set_password(password)
        
        # Update other fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        
        instance.save()
        logger.info(f"User updated: {instance.email}")
        return instance


class ConversationListSerializer(DynamicFieldsModelSerializer, TimestampMixin):
    """
    Serializer for conversation list views.
    
    Optimized for displaying conversations with participant info and last message.
    """
    
    participant_count = serializers.SerializerMethodField()
    last_message_preview = serializers.SerializerMethodField()
    unread_count = serializers.SerializerMethodField()
    is_participant = serializers.SerializerMethodField()
    created_by_name = serializers.CharField(source='created_by.display_name', read_only=True)
    
    class Meta:
        model = Conversation
        fields = [
            'id', 'name', 'conversation_type', 'participant_count', 'last_message_preview',
            'unread_count', 'status', 'is_active', 'last_message_at', 'created_by_name',
            'created_at', 'updated_at', 'is_participant'
        ]
    
    def get_participant_count(self, obj):
        return obj.participants.count()
    
    def get_last_message_preview(self, obj):
        if obj.last_message:
            content = obj.last_message.content[:50]
            if len(obj.last_message.content) > 50:
                content += '...'
            return content
        return None
    
    def get_unread_count(self, obj):
        user = self.context.get('request').user
        if user.is_authenticated:
            return obj.get_unread_count_for_user(user)
        return 0
    
    def get_is_participant(self, obj):
        user = self.context.get('request').user
        if user.is_authenticated:
            return obj.is_participant(user)
        return False


class ConversationDetailSerializer(DynamicFieldsModelSerializer, TimestampMixin):
    """
    Serializer for detailed conversation views.
    
    Includes all participants, messages, and settings.
    """
    
    participants = UserProfileSerializer(many=True, read_only=True)
    participant_count = serializers.IntegerField(source='get_participant_count', read_only=True)
    unread_count = serializers.SerializerMethodField()
    can_manage = serializers.SerializerMethodField()
    created_by_name = serializers.CharField(source='created_by.display_name', read_only=True)
    last_message_info = serializers.SerializerMethodField()
    
    class Meta:
        model = Conversation
        fields = [
            'id', 'name', 'description', 'conversation_type', 'image', 'participants',
            'participant_count', 'unread_count', 'status', 'is_active', 'is_private',
            'allow_file_sharing', 'allow_voice_messages', 'message_retention_days',
            'last_message', 'last_message_info', 'last_message_at', 'created_by', 'created_by_name',
            'created_at', 'updated_at', 'can_manage'
        ]
        read_only_fields = [
            'id', 'participant_count', 'unread_count', 'last_message', 'created_by', 'created_at', 'updated_at'
        ]
    
    def get_unread_count(self, obj):
        user = self.context.get('request').user
        if user.is_authenticated:
            return obj.get_unread_count_for_user(user)
        return 0
    
    def get_can_manage(self, obj):
        user = self.context.get('request').user
        if user.is_authenticated:
            return (obj.created_by == user or user.is_staff)
        return False
    
    def get_last_message_info(self, obj):
        if obj.last_message:
            return {
                'id': obj.last_message.id,
                'content': obj.last_message.content[:100],
                'sender': obj.last_message.sender.display_name,
                'created_at': obj.last_message.created_at.isoformat() if obj.last_message.created_at else None
            }
        return None


class MessageSerializer(DynamicFieldsModelSerializer, TimestampMixin, NestedSerializerMixin):
    """
    Serializer for message data.
    
    Handles message content, attachments, threading, and status.
    """
    
    sender = UserProfileSerializer(read_only=True)
    thread_info = serializers.SerializerMethodField()
    attachments = serializers.SerializerMethodField()
    conversation_name = serializers.CharField(source='conversation.name', read_only=True)
    reply_count = serializers.SerializerMethodField()
    can_edit = serializers.SerializerMethodField()
    can_delete = serializers.SerializerMethodField()
    formatted_created_at = serializers.SerializerMethodField()
    formatted_edited_at = serializers.SerializerMethodField()
    
    class Meta:
        model = Message
        fields = [
            'id', 'conversation', 'conversation_name', 'thread', 'thread_info',
            'sender', 'recipient', 'content', 'message_type', 'is_edited', 'original_content',
            'formatted_edited_at', 'is_read', 'read_at', 'is_delivered', 'delivered_at',
            'is_deleted', 'deleted_at', 'formatted_created_at', 'expires_at',
            'is_important', 'is_urgent', 'priority', 'attachments', 'reply_count',
            'can_edit', 'can_delete', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'sender', 'is_read', 'read_at', 'is_delivered', 'delivered_at',
            'is_deleted', 'deleted_at', 'formatted_created_at', 'updated_at'
        ]
    
    def get_thread_info(self, obj):
        if obj.thread:
            return {
                'id': obj.thread.id,
                'subject': obj.thread.subject,
                'depth': obj.get_thread_depth()
            }
        return None
    
    def get_attachments(self, obj):
        """Get message attachments with detailed information."""
        attachments = obj.get_attachments()
        return [
            {
                'id': attachment.id,
                'filename': attachment.filename,
                'file_type': attachment.file_type,
                'file_size': attachment.file_size,
                'human_readable_size': attachment.human_readable_size,
                'url': attachment.file.url if attachment.file else None,
                'mime_type': attachment.mime_type
            }
            for attachment in attachments
        ]
    
    def get_reply_count(self, obj):
        if obj.thread:
            return obj.thread.get_all_replies().count()
        return 0
    
    def get_can_edit(self, obj):
        user = self.context.get('request').user
        if user.is_authenticated:
            return obj.sender == user
        return False
    
    def get_can_delete(self, obj):
        user = self.context.get('request').user
        if user.is_authenticated:
            return obj.sender == user
        return False
    
    def get_formatted_created_at(self, obj):
        return self.get_timestamp(obj, 'created_at')
    
    def get_formatted_edited_at(self, obj):
        if obj.is_edited and obj.edited_at:
            return self.get_timestamp(obj, 'edited_at')
        return None
    
    def validate_content(self, value):
        """Validate message content."""
        if value:
            validate_content_length(value, max_length=10000)  # Allow longer messages
            
            # Basic content validation
            if value.strip() == '':
                raise serializers.ValidationError("Message content cannot be empty.")
        return value
    
    def validate_message_type(self, value):
        """Validate message type."""
        valid_types = dict(Message.TYPE_CHOICES).keys()
        if value not in valid_types:
            raise serializers.ValidationError(f"Invalid message type. Must be one of: {', '.join(valid_types)}")
        return value
    
    def validate(self, data):
        """Validate message data."""
        # Ensure user is a participant in the conversation
        conversation = data.get('conversation')
        user = self.context.get('request').user
        
        if conversation and user.is_authenticated:
            if not conversation.is_participant(user):
                raise serializers.ValidationError("You must be a participant in the conversation to send messages.")
        
        # Validate thread relationship
        thread = data.get('thread')
        if thread and conversation:
            if thread.conversation != conversation:
                raise serializers.ValidationError("Thread must belong to the specified conversation.")
        
        return data


class NotificationSerializer(DynamicFieldsModelSerializer, TimestampMixin):
    """
    Serializer for notification data.
    
    Handles notification content, status, and user preferences.
    """
    
    user_info = serializers.SerializerMethodField()
    sender_info = serializers.SerializerMethodField()
    category_info = serializers.SerializerMethodField()
    formatted_scheduled_at = serializers.SerializerMethodField()
    formatted_sent_at = serializers.SerializerMethodField()
    formatted_read_at = serializers.SerializerMethodField()
    
    class Meta:
        model = Notification
        fields = [
            'id', 'user', 'user_info', 'sender', 'sender_info', 'title', 'message',
            'category', 'category_info', 'priority', 'related_object_type', 'related_object_id',
            'action_url', 'image_url', 'extra_data', 'status', 'scheduled_at', 'formatted_scheduled_at',
            'sent_at', 'formatted_sent_at', 'delivered_at', 'read_at', 'formatted_read_at',
            'is_read', 'is_archived', 'is_clicked', 'clicked_at', 'is_dismissed', 'dismissed_at',
            'created_at'
        ]
        read_only_fields = [
            'id', 'user', 'sender', 'status', 'sent_at', 'delivered_at', 'created_at'
        ]
    
    def get_user_info(self, obj):
        return {
            'id': obj.user.id,
            'email': obj.user.email,
            'display_name': obj.user.display_name
        }
    
    def get_sender_info(self, obj):
        if obj.sender:
            return {
                'id': obj.sender.id,
                'email': obj.sender.email,
                'display_name': obj.sender.display_name
            }
        return None
    
    def get_category_info(self, obj):
        return {
            'id': obj.category.id,
            'name': obj.category.name,
            'color': obj.category.color,
            'icon': obj.category.icon
        }
    
    def get_formatted_scheduled_at(self, obj):
        return self.get_timestamp(obj, 'scheduled_at')
    
    def get_formatted_sent_at(self, obj):
        return self.get_timestamp(obj, 'sent_at')
    
    def get_formatted_read_at(self, obj):
        return self.get_timestamp(obj, 'read_at')
    
    def validate_priority(self, value):
        """Validate priority level."""
        valid_priorities = dict(Notification.PRIORITY_CHOICES).keys()
        if value not in valid_priorities:
            raise serializers.ValidationError(f"Invalid priority. Must be one of: {', '.join(valid_priorities)}")
        return value


# List serializers for improved performance
class UserListSerializer(DynamicFieldsModelSerializer):
    """
    Simplified serializer for user list views.
    """
    
    class Meta:
        model = UserModel
        fields = ['id', 'email', 'username', 'display_name', 'profile_picture', 'is_online', 'is_verified']


class MessageListSerializer(DynamicFieldsModelSerializer):
    """
    Simplified serializer for message list views.
    """
    
    sender = UserListSerializer(read_only=True)
    conversation_name = serializers.CharField(source='conversation.name', read_only=True)
    
    class Meta:
        model = Message
        fields = [
            'id', 'conversation', 'conversation_name', 'sender', 'content',
            'message_type', 'is_read', 'is_edited', 'is_important', 'created_at'
        ]


class NotificationListSerializer(DynamicFieldsModelSerializer):
    """
    Simplified serializer for notification list views.
    """
    
    category_info = serializers.SerializerMethodField()
    sender_info = serializers.SerializerMethodField()
    
    class Meta:
        model = Notification
        fields = [
            'id', 'title', 'message', 'category_info', 'sender_info',
            'priority', 'status', 'is_read', 'is_clicked', 'action_url',
            'created_at'
        ]
    
    def get_category_info(self, obj):
        return {
            'id': obj.category.id,
            'name': obj.category.name,
            'color': obj.category.color
        }
    
    def get_sender_info(self, obj):
        if obj.sender:
            return {
                'id': obj.sender.id,
                'display_name': obj.sender.display_name
            }
        return None