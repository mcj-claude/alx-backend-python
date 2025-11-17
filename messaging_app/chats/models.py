"""
Django Database Schema for Messaging Platform

This module implements three core models for a messaging platform:
- User (Extended AbstractBaseUser)
- Conversation 
- Message

Following Django ORM best practices with robust validation,
referential integrity, and optimized indexing for large-scale operations.
"""

import uuid
from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.core.exceptions import ValidationError
from django.core.validators import validate_email, RegexValidator
from django.utils import timezone
from django.conf import settings


class UserRole(models.TextChoices):
    """User role enumeration for the messaging platform."""
    GUEST = 'guest', 'Guest'
    HOST = 'host', 'Host'
    ADMIN = 'admin', 'Admin'


class UserManager(BaseUserManager):
    """
    Custom manager for User model extending AbstractBaseUser.
    
    Provides methods for user creation and authentication with
    proper validation and password handling.
    """
    
    def create_user(self, email, password=None, **extra_fields):
        """Create and return a regular user with an email and password."""
        if not email:
            raise ValueError('Email address is required')
        
        # Normalize email address
        email = self.normalize_email(email)
        
        # Create user instance
        user = self.model(email=email, **extra_fields)
        
        # Validate required fields
        if not extra_fields.get('first_name'):
            raise ValueError('First name is required')
        if not extra_fields.get('last_name'):
            raise ValueError('Last name is required')
        if not extra_fields.get('role'):
            raise ValueError('Role is required')
        
        # Set password and save
        user.set_password(password)
        user.full_clean()
        user.save(using=self._db)
        
        return user
    
    def create_superuser(self, email, password, first_name, last_name, **extra_fields):
        """Create and return a superuser with admin privileges."""
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('role', UserRole.ADMIN)
        
        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True')
        
        return self.create_user(
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name,
            **extra_fields
        )


class User(AbstractBaseUser, PermissionsMixin):
    """
    Extended User model for the messaging platform.
    
    Extends Django's AbstractBaseUser with custom authentication fields,
    role-based permissions, and comprehensive validation.
    
    Database Schema:
    - user_id (UUID, PK, Indexed)
    - email (VARCHAR, UNIQUE, NOT NULL)
    - password_hash (VARCHAR, NOT NULL)
    - first_name (VARCHAR, NOT NULL)
    - last_name (VARCHAR, NOT NULL)
    - phone_number (VARCHAR, NULL)
    - role (ENUM: guest/host/admin, NOT NULL)
    - created_at (TIMESTAMP, DEFAULT CURRENT_TIMESTAMP)
    """
    
    # Primary Key - UUID for scalability
    user_id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Unique identifier for the user account"
    )
    
    # Authentication Fields
    email = models.EmailField(
        unique=True,
        validators=[validate_email],
        help_text="Email address used for authentication"
    )
    
    # Required Profile Fields
    first_name = models.CharField(
        max_length=150,
        help_text="User's first name"
    )
    last_name = models.CharField(
        max_length=150,
        help_text="User's last name"
    )
    
    # Optional Profile Fields
    phone_number = models.CharField(
        max_length=20,
        null=True,
        blank=True,
        validators=[
            RegexValidator(
                regex=r'^\+?[1-9]\d{1,14}$',
                message="Phone number must be in international format"
            )
        ],
        help_text="Phone number in international format"
    )
    
    # Role-based Access Control
    role = models.CharField(
        max_length=10,
        choices=UserRole.choices,
        default=UserRole.HOST,
        help_text="User role determining platform access level"
    )
    
    # Audit Fields
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="Timestamp when user account was created"
    )
    
    # Django Authentication Fields
    is_staff = models.BooleanField(
        default=False,
        help_text="Designates whether the user can log into Django admin"
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Designates whether this user should be treated as active"
    )
    
    # Manager and Authentication Configuration
    objects = UserManager()
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['first_name', 'last_name', 'role']
    
    class Meta:
        """Database configuration for User model."""
        db_table = 'users'
        verbose_name = 'User'
        verbose_name_plural = 'Users'
        
        # Indexing Strategy
        indexes = [
            models.Index(fields=['email'], name='user_email_idx'),
            models.Index(fields=['role'], name='user_role_idx'),
            models.Index(fields=['created_at'], name='user_created_idx'),
            models.Index(fields=['is_active'], name='user_active_idx'),
        ]
        
        # Constraints for Data Integrity
        constraints = [
            models.CheckConstraint(
                check=models.Q(role__in=UserRole.values),
                name='valid_user_role'
            ),
            models.UniqueConstraint(
                fields=['email'],
                name='unique_user_email'
            ),
        ]
        
        # Ordering
        ordering = ['-created_at']
    
    def __str__(self):
        """String representation of the user."""
        return f"{self.first_name} {self.last_name} ({self.email})"
    
    def clean(self):
        """Validate user model data."""
        super().clean()
        
        # Additional validation beyond field validators
        if self.email:
            self.email = self.normalize_email(self.email)
        
        # Validate role selection
        if self.role not in UserRole.values:
            raise ValidationError({
                'role': f'Invalid role. Must be one of: {", ".join(UserRole.values)}'
            })
    
    @property
    def display_name(self):
        """Return user's display name."""
        return f"{self.first_name} {self.last_name}".strip()
    
    def can_create_conversations(self):
        """Check if user can create conversations (host or admin)."""
        return self.role in [UserRole.HOST, UserRole.ADMIN]
    
    def has_moderation_permissions(self):
        """Check if user has moderation privileges (admin only)."""
        return self.role == UserRole.ADMIN


class ConversationParticipant(models.Model):
    """
    Through table for many-to-many relationship between User and Conversation.
    
    Manages participant relationships with additional metadata
    for conversation administration and read tracking.
    """
    
    conversation = models.ForeignKey(
        'Conversation',
        on_delete=models.CASCADE,
        related_name='conversation_participants'
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='conversation_participants'
    )
    joined_at = models.DateTimeField(auto_now_add=True)
    is_admin = models.BooleanField(default=False)
    last_read_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        """Database configuration for ConversationParticipant."""
        db_table = 'conversation_participants'
        verbose_name = 'Conversation Participant'
        verbose_name_plural = 'Conversation Participants'
        unique_together = [('conversation', 'user')]
        
        # Indexing for performance
        indexes = [
            models.Index(fields=['conversation'], name='cp_conversation_idx'),
            models.Index(fields=['user'], name='cp_user_idx'),
            models.Index(fields=['joined_at'], name='cp_joined_idx'),
            models.Index(fields=['is_admin'], name='cp_admin_idx'),
        ]
    
    def __str__(self):
        """String representation of the participant relationship."""
        return f"{self.user.display_name} in {self.conversation.conversation_id}"


class Conversation(models.Model):
    """
    Conversation model for group and direct message conversations.
    
    Database Schema:
    - conversation_id (UUID, PK, Indexed)
    - created_at (TIMESTAMP, DEFAULT CURRENT_TIMESTAMP)
    """
    
    # Primary Key - UUID for scalability
    conversation_id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Unique identifier for the conversation"
    )
    
    # Many-to-Many relationship to User via explicit relationship model
    participants = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        through='ConversationParticipant',
        related_name='conversations',
        help_text="Users participating in this conversation"
    )
    
    # Audit Fields
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="Timestamp when conversation was created"
    )
    
    # Additional metadata
    title = models.CharField(
        max_length=255,
        blank=True,
        help_text="Optional conversation title"
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Whether the conversation is active"
    )
    
    class Meta:
        """Database configuration for Conversation model."""
        db_table = 'conversations'
        verbose_name = 'Conversation'
        verbose_name_plural = 'Conversations'
        
        # Indexing Strategy
        indexes = [
            models.Index(fields=['conversation_id'], name='conversation_id_idx'),
            models.Index(fields=['created_at'], name='conversation_created_idx'),
            models.Index(fields=['is_active'], name='conversation_active_idx'),
        ]
        
        # Ordering
        ordering = ['-created_at']
    
    def __str__(self):
        """String representation of the conversation."""
        if self.title:
            return f"{self.title} ({self.conversation_id})"
        else:
            # Show first 3 participant names
            participant_names = [
                p.display_name for p in 
                self.participants.all()[:3]
            ]
            participant_str = ", ".join(participant_names)
            return f"Conversation: {participant_str} ({self.conversation_id})"
    
    def clean(self):
        """Validate conversation data."""
        super().clean()
        
        # Validate that conversation has at least 2 participants if already created
        if self.pk:
            participant_count = self.participants.count()
            if participant_count < 2:
                raise ValidationError(
                    "A conversation must have at least 2 participants"
                )
    
    def add_participant(self, user, is_admin=False):
        """Add a participant to this conversation."""
        if not self.participants.filter(id=user.id).exists():
            ConversationParticipant.objects.create(
                conversation=self,
                user=user,
                is_admin=is_admin
            )
    
    def remove_participant(self, user):
        """Remove a participant from this conversation."""
        if self.participants.filter(id=user.id).exists():
            # Check if removing this user would leave less than 2 participants
            if self.participants.count() <= 2:
                raise ValidationError(
                    "Cannot remove participant: minimum 2 participants required"
                )
            self.participants.remove(user)
    
    def get_participant_count(self):
        """Get current number of participants."""
        return self.participants.count()
    
    def is_participant(self, user):
        """Check if a user is a participant in this conversation."""
        return self.participants.filter(id=user.id).exists()
    
    def get_message_count(self):
        """Get total number of messages in this conversation."""
        return self.messages.count()


class Message(models.Model):
    """
    Message model for individual messages within conversations.
    
    Database Schema:
    - message_id (UUID, PK, Indexed)
    - sender_id (Foreign Key to User, NOT NULL)
    - conversation_id (Foreign Key to Conversation, NOT NULL)
    - message_body (TEXT, NOT NULL)
    - sent_at (TIMESTAMP, DEFAULT CURRENT_TIMESTAMP)
    """
    
    # Primary Key - UUID for scalability
    message_id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Unique identifier for the message"
    )
    
    # Foreign Key Relationships
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='sent_messages',
        help_text="User who sent this message"
    )
    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name='messages',
        help_text="Conversation this message belongs to"
    )
    
    # Message Content
    message_body = models.TextField(
        help_text="Content of the message"
    )
    
    # Timestamp
    sent_at = models.DateTimeField(
        auto_now_add=True,
        help_text="Timestamp when message was sent"
    )
    
    # Additional metadata
    is_deleted = models.BooleanField(
        default=False,
        help_text="Whether this message has been deleted"
    )
    deleted_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp when message was deleted"
    )
    reply_to = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='replies',
        help_text="Message this is a reply to"
    )
    
    class Meta:
        """Database configuration for Message model."""
        db_table = 'messages'
        verbose_name = 'Message'
        verbose_name_plural = 'Messages'
        
        # Indexing Strategy for optimized queries
        indexes = [
            models.Index(fields=['message_id'], name='message_id_idx'),
            models.Index(fields=['conversation'], name='message_conversation_idx'),
            models.Index(fields=['sender'], name='message_sender_idx'),
            models.Index(fields=['sent_at'], name='message_sent_at_idx'),
            # Composite indexes for common query patterns
            models.Index(
                fields=['conversation', 'sent_at'],
                name='message_conversation_sent_idx'
            ),
            models.Index(
                fields=['sender', 'sent_at'],
                name='message_sender_sent_idx'
            ),
            models.Index(
                fields=['conversation', 'is_deleted', 'sent_at'],
                name='message_conversation_deleted_sent_idx'
            ),
        ]
        
        # Constraints for Data Integrity
        constraints = [
            models.CheckConstraint(
                check=models.Q(message_body__isnull=False) & models.Q(message_body__gt=''),
                name='non_empty_message_body'
            ),
            models.CheckConstraint(
                check=models.Q(message_body__length__lte=5000),
                name='message_body_length_limit'
            ),
        ]
        
        # Ordering for efficient retrieval
        ordering = ['-sent_at']
    
    def __str__(self):
        """String representation of the message."""
        content_preview = self.message_body[:50]
        if len(self.message_body) > 50:
            content_preview += "..."
        return f"Message from {self.sender.display_name}: {content_preview}"
    
    def clean(self):
        """Validate message data."""
        super().clean()
        
        # Validate that sender is participant in conversation
        if self.conversation and self.sender:
            if not self.conversation.is_participant(self.sender):
                raise ValidationError(
                    f"Sender {self.sender.email} is not a participant in this conversation"
                )
    
    def save(self, *args, **kwargs):
        """Save message with validation."""
        # Set deleted_at when message is marked as deleted
        if self.is_deleted and not self.deleted_at:
            self.deleted_at = timezone.now()
        
        # Validate before save
        self.full_clean()
        super().save(*args, **kwargs)
    
    def soft_delete(self):
        """Mark message as deleted (soft delete)."""
        if not self.is_deleted:
            self.is_deleted = True
            self.deleted_at = timezone.now()
            self.save(update_fields=['is_deleted', 'deleted_at'])
    
    def get_thread_depth(self):
        """Get the depth of this message in the reply thread."""
        depth = 0
        current = self.reply_to
        while current:
            depth += 1
            current = current.reply_to
        return depth