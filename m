"""
Django REST Framework serializers for messaging platform models.

Provides comprehensive serialization for User, Conversation, and Message models
with proper validation and nested relationships.
"""

from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.db import transaction
from django.core.exceptions import ValidationError

from .models import User, Conversation, Message, ConversationParticipant, UserRole


class UserSerializer(serializers.ModelSerializer):
    """
    Serializer for User model with extended fields.
    
    Handles user profile information with role-based visibility
    and authentication-related fields.
    """
    password = serializers.CharField(write_only=True, required=False)
    password_confirm = serializers.CharField(write_only=True, required=False)
    display_name = serializers.CharField(source='display_name', read_only=True)
    
    class Meta:
        model = User
        fields = [
            'user_id', 'email', 'first_name', 'last_name', 'display_name',
            'phone_number', 'role', 'is_active', 'created_at', 'password',
            'password_confirm'
        ]
        read_only_fields = ['user_id', 'is_active', 'created_at']
    
    def validate_email(self, value):
        """Validate email uniqueness."""
        # If updating, exclude current user from uniqueness check
        if self.instance:
            if User.objects.filter(email__iexact=value).exclude(id=self.instance.user_id).exists():
                raise serializers.ValidationError("A user with this email already exists.")
        else:
            if User.objects.filter(email__iexact=value).exists():
                raise serializers.ValidationError("A user with this email already exists.")
        return value
    
    def validate_role(self, value):
        """Validate role selection."""
        if value not in UserRole.values:
            raise serializers.ValidationError(f"Invalid role. Must be one of: {', '.join(UserRole.values)}")
        return value
    
    def validate_password(self, value):
        """Validate password strength."""
        if value and len(value) < 8:
            raise serializers.ValidationError("Password must be at least 8 characters long.")
        return value
    
    def validate(self, data):
        """Cross-field validation for password confirmation."""
        # Only validate password confirmation during user creation
        if 'password' in data or 'password_confirm' in data:
            password = data.get('password', '')
            password_confirm = data.get('password_confirm', '')
            
            if password != password_confirm:
                raise serializers.ValidationError({
                    'password_confirm': 'Passwords do not match.'
                })
        
        return data
    
    def create(self, validated_data):
        """Create user with password handling."""
        password = validated_data.pop('password', None)
        validated_data.pop('password_confirm', None)
        
        user = User.objects.create_user(
            email=validated_data['email'],
            password=password,
            **validated_data
        )
        
        return user
    
    def update(self, instance, validated_data):
        """Update user with password handling."""
        password = validated_data.pop('password', None)
        validated_data.pop('password_confirm', None)
        
        # Update user fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        
        # Update password if provided
        if password:
            instance.set_password(password)
        
        instance.save()
        return instance


class ConversationParticipantSerializer(serializers.ModelSerializer):
    """
    Serializer for ConversationParticipant through model.
    
    Handles participant information within conversations.
    """
    user_info = UserSerializer(source='user', read_only=True)
    
    class Meta:
        model = ConversationParticipant
        fields = ['id', 'user_info', 'joined_at', 'is_admin', 'last_read_at']
        read_only_fields = ['id', 'joined_at', 'user_info']


class ConversationListSerializer(serializers.ModelSerializer):
    """
    Serializer for conversation list view.
    
    Provides lightweight serialization for conversation listing
    with participant count and message count.
    """
    participant_count = serializers.SerializerMethodField()
    unread_count = serializers.SerializerMethodField()
    last_message = serializers.SerializerMethodField()
    
    class Meta:
        model = Conversation
        fields = [
            'conversation_id', 'title', 'participant_count', 
            'message_count', 'created_at', 'unread_count', 'last_message'
        ]
        read_only_fields = ['conversation_id', 'message_count']
    
    def get_participant_count(self, obj):
        """Get number of participants in conversation."""
        return obj.participants.count()
    
    def get_unread_count(self, obj):
        """Get unread message count for current user."""
        user = self.context.get('request').user if self.context.get('request') else None
        if user:
            return obj.messages.filter(
                is_deleted=False,
                is_read=False
            ).exclude(sender=user).count()
        return 0
    
    def get_last_message(self, obj):
        """Get last message in conversation."""
        last_msg = obj.messages.filter(is_deleted=False).order_by('-sent_at').first()
        if last_msg:
            return {
                'message_id': last_msg.message_id,
                'content': last_msg.message_body[:100] + ('...' if len(last_msg.message_body) > 100 else ''),
                'sender': {
                    'user_id': last_msg.sender.user_id,
                    'first_name': last_msg.sender.first_name,
                    'last_name': last_msg.sender.last_name,
                    'display_name': last_msg.sender.display_name
                },
                'sent_at': last_msg.sent_at
            }
        return None


class ConversationSerializer(serializers.ModelSerializer):
    """
    Full serializer for Conversation model.
    
    Handles conversation creation and detailed retrieval
    with participant management.
    """
    participants = UserSerializer(many=True, read_only=True)
    participant_ids = serializers.PrimaryKeyRelatedField(
        many=True, 
        queryset=User.objects.all(),
        write_only=True,
        required=False,
        source='participants'
    )
    admin_participants = serializers.SerializerMethodField()
    conversation_admin_participants = serializers.SerializerMethodField()
    message_count = serializers.SerializerMethodField()
    last_message = serializers.SerializerMethodField()
    
    class Meta:
        model = Conversation
        fields = [
            'conversation_id', 'title', 'participants', 'participant_ids',
            'admin_participants', 'conversation_admin_participants',
            'message_count', 'last_message', 'created_at', 'is_active'
        ]
        read_only_fields = ['conversation_id', 'message_count', 'last_message', 'created_at']
    
    def get_admin_participants(self, obj):
        """Get list of admin participants."""
        admins = obj.participants.filter(is_staff=True) | obj.participants.filter(role=UserRole.ADMIN)
        return UserSerializer(admins, many=True).data
    
    def get_conversation_admin_participants(self, obj):
        """Get list of conversation admin participants."""
        admins = obj.conversation_participants.filter(is_admin=True).values_list('user_id', flat=True)
        return User.objects.filter(id__in=admins).values_list('user_id', flat=True)
    
    def get_message_count(self, obj):
        """Get total message count."""
        return obj.messages.filter(is_deleted=False).count()
    
    def get_last_message(self, obj):
        """Get last message in conversation."""
        last_msg = obj.messages.filter(is_deleted=False).order_by('-sent_at').first()
        if last_msg:
            return MessageListSerializer(last_msg, context={'request': self.context.get('request')}).data
        return None
    
    def validate_participant_ids(self, value):
        """Validate participant IDs."""
        if len(value) < 1:
            raise serializers.ValidationError("At least one participant is required.")
        return value
    
    def create(self, validated_data):
        """Create conversation with participants."""
        participant_ids = validated_data.pop('participants', [])
        
        with transaction.atomic():
            # Create conversation
            conversation = Conversation.objects.create(**validated_data)
            
            # Add creator as participant
            conversation.add_participant(self.context['request'].user, is_admin=True)
            
            # Add other participants
            for participant_id in participant_ids:
                try:
                    user = User.objects.get(id=participant_id)
                    conversation.add_participant(user)
                except User.DoesNotExist:
                    continue
        
        return conversation
    
    def update(self, instance, validated_data):
        """Update conversation (only title/description)."""
        participant_ids = validated_data.pop('participants', None)
        
        # Update conversation fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        
        instance.save()
        
        return instance


class MessageListSerializer(serializers.ModelSerializer):
    """
    Serializer for message list view.
    
    Provides lightweight serialization for message listing
    with sender information.
    """
    sender_info = UserSerializer(source='sender', read_only=True)
    reply_to_info = serializers.SerializerMethodField()
    
    class Meta:
        model = Message
        fields = [
            'message_id', 'message_body', 'sender_info', 'reply_to_info',
            'sent_at', 'is_deleted', 'deleted_at'
        ]
        read_only_fields = [
            'message_id', 'sent_at', 'is_deleted', 'deleted_at'
        ]
    
    def get_reply_to_info(self, obj):
        """Get information about message being replied to."""
        if obj.reply_to and not obj.reply_to.is_deleted:
            return {
                'message_id': obj.reply_to.message_id,
                'content': obj.reply_to.message_body[:100] + ('...' if len(obj.reply_to.message_body) > 100 else ''),
                'sender': {
                    'user_id': obj.reply_to.sender.user_id,
                    'first_name': obj.reply_to.sender.first_name,
                    'last_name': obj.reply_to.sender.last_name,
                    'display_name': obj.reply_to.sender.display_name
                }
            }
        return None


class MessageSerializer(serializers.ModelSerializer):
    """
    Full serializer for Message model.
    
    Handles message creation, update, and detailed retrieval
    with conversation validation.
    """
    sender_info = UserSerializer(source='sender', read_only=True)
    conversation_info = serializers.SerializerMethodField()
    reply_to_info = MessageListSerializer(source='reply_to', read_only=True)
    can_edit = serializers.SerializerMethodField()
    can_delete = serializers.SerializerMethodField()
    
    class Meta:
        model = Message
        fields = [
            'message_id', 'message_body', 'sender', 'conversation', 'reply_to',
            'reply_to_info', 'sent_at', 'is_deleted', 'deleted_at',
            'sender_info', 'conversation_info', 'can_edit', 'can_delete'
        ]
        read_only_fields = [
            'message_id', 'sent_at', 'is_deleted', 'deleted_at',
            'sender_info', 'conversation_info', 'can_edit', 'can_delete'
        ]
    
    def get_conversation_info(self, obj):
        """Get conversation information."""
        return {
            'conversation_id': obj.conversation.conversation_id,
            'title': obj.conversation.title,
            'participant_count': obj.conversation.participants.count()
        }
    
    def get_can_edit(self, obj):
        """Check if current user can edit this message."""
        user = self.context.get('request').user if self.context.get('request') else None
        return user and obj.sender == user and not obj.is_deleted
    
    def get_can_delete(self, obj):
        """Check if current user can delete this message."""
        user = self.context.get('request').user if self.context.get('request') else None
        if not user or obj.is_deleted:
            return False
        
        # Sender can delete their own messages
        if obj.sender == user:
            return True
        
        # Conversation admins can delete any message
        return obj.conversation.get_admin_participants().filter(id=user.id).exists()
    
    def validate_message_body(self, value):
        """Validate message content."""
        content = value.strip() if value else ''
        if not content:
            raise serializers.ValidationError("Message content cannot be empty.")
        if len(content) > 5000:
            raise serializers.ValidationError("Message content cannot exceed 5000 characters.")
        return content
    
    def validate(self, data):
        """Validate message creation."""
        sender = data.get('sender')
        conversation = data.get('conversation')
        reply_to = data.get('reply_to')
        
        # Validate sender is participant in conversation
        if sender and conversation:
            if not conversation.is_participant(sender):
                raise serializers.ValidationError(
                    "Sender must be a participant in the conversation."
                )
        
        # Validate reply_to message
        if reply_to:
            if reply_to.conversation != conversation:
                raise serializers.ValidationError(
                    "Reply message must be from the same conversation."
                )
            if reply_to.is_deleted:
                raise serializers.ValidationError(
                    "Cannot reply to a deleted message."
                )
        
        return data
    
    def create(self, validated_data):
        """Create message with validation."""
        sender = validated_data['sender']
        conversation = validated_data['conversation']
        
        # Create message
        message = Message.objects.create(**validated_data)
        
        # Update conversation's last message
        conversation.update_last_message(message)
        
        return message
    
    def update(self, instance, validated_data):
        """Update message (only message body for now)."""
        if instance.sender != self.context['request'].user:
            raise serializers.ValidationError("You can only edit your own messages.")
        
        # Update message body
        instance.message_body = validated_data.get('message_body', instance.message_body)
        instance.edit_content(instance.message_body)
        
        return instance