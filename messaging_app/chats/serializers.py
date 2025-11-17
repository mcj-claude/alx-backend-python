"""
Django REST Framework serializers for the messaging platform.

Provides comprehensive serialization for User, Conversation, and Message models
with proper nested relationships and validation.
"""

from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.utils import timezone

from .models import (
    User, 
    Conversation, 
    Message, 
    ConversationParticipant,
    UserRole
)


User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    """
    Serializer for User model with profile information.
    
    Includes user profile data with proper field validation
    and custom representation for API responses.
    """
    password = serializers.CharField(write_only=True, required=False)
    password_confirm = serializers.CharField(write_only=True, required=False)
    full_name = serializers.CharField(source='get_full_name', read_only=True)
    
    class Meta:
        model = User
        fields = [
            'user_id', 'email', 'username', 'first_name', 'last_name',
            'full_name', 'phone_number', 'bio', 'profile_picture',
            'role', 'is_verified', 'is_active', 'created_at', 'updated_at',
            'last_login', 'password', 'password_confirm'
        ]
        read_only_fields = [
            'user_id', 'created_at', 'updated_at', 'last_login', 'is_verified'
        ]
    
    def validate_email(self, value):
        """Validate email uniqueness."""
        if self.instance and self.instance.email == value:
            return value
        
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return value
    
    def validate(self, attrs):
        """Validate password confirmation for new users."""
        if self.instance:  # Updating existing user
            return attrs
        
        password = attrs.get('password')
        password_confirm = attrs.get('password_confirm')
        
        if password and password_confirm:
            if password != password_confirm:
                raise serializers.ValidationError("Password confirmation doesn't match password.")
        
        if not password:
            raise serializers.ValidationError("Password is required for new users.")
        
        return attrs
    
    def create(self, validated_data):
        """Create new user with validated data."""
        validated_data.pop('password_confirm', None)
        password = validated_data.pop('password')
        
        user = User.objects.create_user(password=password, **validated_data)
        return user
    
    def update(self, instance, validated_data):
        """Update user with proper password handling."""
        validated_data.pop('password_confirm', None)
        password = validated_data.pop('password', None)
        
        if password:
            instance.set_password(password)
        
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        
        instance.save()
        return instance


class ConversationParticipantSerializer(serializers.ModelSerializer):
    """
    Serializer for ConversationParticipant model.
    
    Used for nested representation of participants in conversations.
    """
    user = UserSerializer(read_only=True)
    joined_at = serializers.DateTimeField(source='created_at', read_only=True)
    
    class Meta:
        model = ConversationParticipant
        fields = [
            'id', 'user', 'role', 'permissions', 'joined_at',
            'last_read_message', 'is_typing'
        ]
        read_only_fields = ['id', 'joined_at', 'last_read_message']


class MessageSerializer(serializers.ModelSerializer):
    """
    Serializer for Message model with conversation threading.
    
    Handles message creation, editing, and display with proper
    foreign key relationships and validation.
    """
    sender = UserSerializer(read_only=True)
    sender_id = serializers.UUIDField(write_only=True)
    conversation_id = serializers.UUIDField(write_only=True)
    conversation = serializers.StringRelatedField(read_only=True)
    reply_to = serializers.SerializerMethodField()
    attachments = serializers.SerializerMethodField()
    
    class Meta:
        model = Message
        fields = [
            'message_id', 'conversation', 'conversation_id',
            'sender', 'sender_id', 'content', 'message_type',
            'reply_to', 'attachments', 'is_read', 'is_edited',
            'sent_at', 'updated_at', 'is_deleted'
        ]
        read_only_fields = [
            'message_id', 'sent_at', 'updated_at', 'is_edited', 
            'is_read', 'is_deleted'
        ]
    
    def get_reply_to(self, obj):
        """Get reply_to message information."""
        if obj.reply_to and not obj.reply_to.is_deleted:
            return {
                'message_id': obj.reply_to.message_id,
                'content': obj.reply_to.content[:100],  # Truncate for preview
                'sender': obj.reply_to.sender.get_full_name() or obj.reply_to.sender.username,
                'sent_at': obj.reply_to.sent_at
            }
        return None
    
    def get_attachments(self, obj):
        """Get message attachments information."""
        from messaging.models import MessageAttachment
        
        attachments = obj.attachments.filter(is_deleted=False)
        return [
            {
                'attachment_id': att.id,
                'filename': att.filename,
                'file_type': att.file_type,
                'file_size': att.file_size,
                'mime_type': att.mime_type,
                'created_at': att.created_at
            }
            for att in attachments
        ]
    
    def validate_content(self, value):
        """Validate message content."""
        if not value.strip():
            raise serializers.ValidationError("Message content cannot be empty.")
        return value.strip()
    
    def validate_conversation_id(self, value):
        """Validate conversation exists."""
        try:
            conversation = Conversation.objects.get(conversation_id=value, is_active=True)
            return value
        except Conversation.DoesNotExist:
            raise serializers.ValidationError("Conversation not found.")
    
    def create(self, validated_data):
        """Create new message with conversation validation."""
        conversation_id = validated_data.pop('conversation_id')
        sender_id = validated_data.pop('sender_id')
        
        try:
            conversation = Conversation.objects.get(conversation_id=conversation_id, is_active=True)
            sender = User.objects.get(user_id=sender_id)
        except (Conversation.DoesNotExist, User.DoesNotExist):
            raise serializers.ValidationError("Invalid conversation or sender.")
        
        # Check if user is participant
        if not conversation.is_participant(sender):
            raise serializers.ValidationError("You are not a participant in this conversation.")
        
        message = Message.objects.create(
            conversation=conversation,
            sender=sender,
            **validated_data
        )
        
        # Update conversation's last activity
        conversation.update_last_message(message)
        
        return message


class ConversationListSerializer(serializers.ModelSerializer):
    """
    Serializer for conversation listing with summary information.
    
    Used for conversation list views with participant info
    and last message preview.
    """
    participant_count = serializers.SerializerMethodField()
    last_message_preview = serializers.SerializerMethodField()
    unread_count = serializers.SerializerMethodField()
    created_by_name = serializers.CharField(source='created_by.display_name', read_only=True)
    
    class Meta:
        model = Conversation
        fields = [
            'conversation_id', 'title', 'conversation_type', 'is_group',
            'participant_count', 'last_message_preview', 'unread_count',
            'created_by_name', 'created_at', 'updated_at', 'is_active'
        ]
        read_only_fields = [
            'conversation_id', 'participant_count', 'last_message_preview',
            'unread_count', 'created_by_name', 'created_at', 'updated_at'
        ]
    
    def get_participant_count(self, obj):
        """Get number of participants in conversation."""
        return obj.participants.count()
    
    def get_last_message_preview(self, obj):
        """Get preview of last message."""
        if obj.last_message and not obj.last_message.is_deleted:
            content = obj.last_message.content[:50]
            if len(obj.last_message.content) > 50:
                content += '...'
            return content
        return None
    
    def get_unread_count(self, obj):
        """Get unread message count for current user."""
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return obj.get_unread_count_for_user(request.user)
        return 0


class ConversationSerializer(serializers.ModelSerializer):
    """
    Serializer for Conversation model with full participant information.
    
    Handles conversation creation, update, and detailed view
    with complete participant list and message count.
    """
    participants = UserSerializer(many=True, read_only=True)
    participant_ids = serializers.ListField(
        child=serializers.UUIDField(),
        write_only=True,
        required=False
    )
    created_by = UserSerializer(read_only=True)
    created_by_id = serializers.UUIDField(write_only=True, required=False)
    message_count = serializers.SerializerMethodField()
    participant_count = serializers.IntegerField(source='participants.count', read_only=True)
    
    class Meta:
        model = Conversation
        fields = [
            'conversation_id', 'title', 'description', 'conversation_type',
            'is_group', 'is_private', 'participants', 'participant_ids',
            'created_by', 'created_by_id', 'created_at', 'updated_at',
            'is_active', 'message_count', 'participant_count'
        ]
        read_only_fields = [
            'conversation_id', 'created_at', 'updated_at', 
            'message_count', 'participant_count'
        ]
    
    def get_message_count(self, obj):
        """Get total message count in conversation."""
        return obj.get_message_count()
    
    def validate_participant_ids(self, value):
        """Validate participant IDs exist and are active."""
        if not value:
            return value
        
        active_users = User.objects.filter(user_id__in=value, is_active=True)
        if active_users.count() != len(value):
            raise serializers.ValidationError("One or more participants are not valid active users.")
        
        return value
    
    def create(self, validated_data):
        """Create new conversation with participants."""
        participant_ids = validated_data.pop('participant_ids', [])
        created_by_id = validated_data.pop('created_by_id', None)
        
        try:
            created_by = User.objects.get(user_id=created_by_id) if created_by_id else None
        except User.DoesNotExist:
            raise serializers.ValidationError("Created_by user not found.")
        
        conversation = Conversation.objects.create(
            created_by=created_by,
            **validated_data
        )
        
        # Add creator as participant if not already included
        if created_by and created_by.user_id not in participant_ids:
            conversation.participants.add(created_by)
        
        # Add other participants
        if participant_ids:
            participants = User.objects.filter(user_id__in=participant_ids)
            conversation.participants.add(*participants)
        
        return conversation
    
    def update(self, instance, validated_data):
        """Update conversation with participant management."""
        participant_ids = validated_data.pop('participant_ids', None)
        
        # Update conversation fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        
        # Update participants if provided
        if participant_ids is not None:
            # Remove existing participants and add new ones
            instance.participants.clear()
            
            # Add creator back if exists
            if instance.created_by:
                instance.participants.add(instance.created_by)
            
            # Add other participants
            participants = User.objects.filter(user_id__in=participant_ids)
            instance.participants.add(*participants)
        
        return instance


class UserListSerializer(serializers.ModelSerializer):
    """
    Serializer for user listing in conversations.
    
    Simplified user representation for participant selection
    and user search results.
    """
    full_name = serializers.CharField(source='get_full_name', read_only=True)
    
    class Meta:
        model = User
        fields = [
            'user_id', 'username', 'email', 'first_name', 'last_name',
            'full_name', 'profile_picture', 'is_verified', 'is_active'
        ]
        read_only_fields = fields