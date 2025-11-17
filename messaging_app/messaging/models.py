from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.core.validators import FileExtensionValidator
import uuid
import os


User = get_user_model()


def message_attachment_upload_path(instance, filename):
    """Generate upload path for message attachments."""
    return f'messages/attachments/{instance.message.id}/{filename}'


def conversation_image_upload_path(instance, filename):
    """Generate upload path for conversation images."""
    return f'conversations/images/{instance.id}/{filename}'


class MessageThread(models.Model):
    """
    Represents a thread of messages within a conversation.
    Supports message threading, reply chains, and message editing.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    conversation = models.ForeignKey('Conversation', on_delete=models.CASCADE, related_name='threads')
    parent_message = models.ForeignKey('self', null=True, blank=True, on_delete=models.CASCADE, related_name='replies')
    subject = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'message_threads'
        indexes = [
            models.Index(fields=['conversation']),
            models.Index(fields=['parent_message']),
            models.Index(fields=['created_at']),
        ]
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Thread: {self.subject or 'No Subject'} ({self.conversation})"
    
    def get_all_replies(self):
        """Get all messages in this thread recursively."""
        replies = []
        for reply in self.replies.all():
            replies.append(reply)
            replies.extend(reply.get_all_replies())
        return replies


class Message(models.Model):
    """
    Represents a message in the messaging system.
    Supports text, attachments, threading, and advanced features.
    """
    TYPE_CHOICES = [
        ('text', 'Text Message'),
        ('image', 'Image'),
        ('file', 'File'),
        ('audio', 'Audio'),
        ('video', 'Video'),
        ('system', 'System Message'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    conversation = models.ForeignKey('Conversation', on_delete=models.CASCADE, related_name='messages')
    thread = models.ForeignKey(MessageThread, null=True, blank=True, on_delete=models.CASCADE, related_name='messages')
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_messages')
    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='received_messages', null=True, blank=True)
    
    # Message Content
    content = models.TextField(blank=True)
    message_type = models.CharField(max_length=10, choices=TYPE_CHOICES, default='text')
    is_edited = models.BooleanField(default=False)
    edited_at = models.DateTimeField(null=True, blank=True)
    original_content = models.TextField(blank=True)  # Store original for editing
    
    # Message Status
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)
    is_delivered = models.BooleanField(default=False)
    delivered_at = models.DateTimeField(null=True, blank=True)
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)
    deleted_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Message Features
    is_important = models.BooleanField(default=False)
    is_urgent = models.BooleanField(default=False)
    priority = models.IntegerField(default=0)  # 0=normal, 1=high, 2=urgent
    expires_at = models.DateTimeField(null=True, blank=True)  # For self-destructing messages
    
    class Meta:
        db_table = 'messages'
        indexes = [
            models.Index(fields=['conversation']),
            models.Index(fields=['sender']),
            models.Index(fields=['recipient']),
            models.Index(fields=['is_read']),
            models.Index(fields=['created_at']),
            models.Index(fields=['message_type']),
            models.Index(fields=['conversation', 'created_at']),
        ]
        ordering = ['-created_at']
        permissions = [
            ('can_edit_messages', 'Can edit messages'),
            ('can_delete_messages', 'Can delete messages'),
            ('can_mark_important', 'Can mark messages as important'),
        ]
    
    def __str__(self):
        return f"Message from {self.sender} at {self.created_at}"
    
    def mark_as_read(self):
        """Mark message as read and update timestamp."""
        if not self.is_read:
            self.is_read = True
            self.read_at = timezone.now()
            self.save(update_fields=['is_read', 'read_at'])
    
    def mark_as_delivered(self):
        """Mark message as delivered and update timestamp."""
        if not self.is_delivered:
            self.is_delivered = True
            self.delivered_at = timezone.now()
            self.save(update_fields=['is_delivered', 'delivered_at'])
    
    def edit_content(self, new_content):
        """Edit message content."""
        if not self.original_content:
            self.original_content = self.content
        self.content = new_content
        self.is_edited = True
        self.edited_at = timezone.now()
        self.save(update_fields=['content', 'is_edited', 'edited_at'])
    
    def soft_delete(self, deleted_by_user):
        """Soft delete the message."""
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.deleted_by = deleted_by_user
        self.save(update_fields=['is_deleted', 'deleted_at', 'deleted_by'])
    
    def is_expired(self):
        """Check if message has expired."""
        return self.expires_at and timezone.now() > self.expires_at
    
    def get_attachments(self):
        """Get all attachments for this message."""
        return self.attachments.filter(is_deleted=False)
    
    def get_thread_depth(self):
        """Get the depth of this message in the thread."""
        depth = 0
        current = self.thread
        while current and current.parent_message:
            depth += 1
            current = current.parent_message
        return depth


class MessageAttachment(models.Model):
    """
    Represents file attachments for messages.
    Supports various file types with size limits and validation.
    """
    FILE_TYPE_CHOICES = [
        ('image', 'Image'),
        ('document', 'Document'),
        ('audio', 'Audio'),
        ('video', 'Video'),
        ('other', 'Other'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    message = models.ForeignKey(Message, on_delete=models.CASCADE, related_name='attachments')
    file = models.FileField(
        upload_to=message_attachment_upload_path,
        validators=[FileExtensionValidator(allowed_extensions=[
            'jpg', 'jpeg', 'png', 'gif', 'bmp', 'svg',  # Images
            'pdf', 'doc', 'docx', 'txt', 'rtf',         # Documents
            'mp3', 'wav', 'ogg', 'm4a',                 # Audio
            'mp4', 'avi', 'mov', 'wmv', 'flv',         # Video
            'zip', 'rar', '7z', 'tar', 'gz',           # Archives
            'csv', 'xls', 'xlsx', 'json', 'xml',       # Data files
        ])]
    )
    filename = models.CharField(max_length=255)
    file_type = models.CharField(max_length=20, choices=FILE_TYPE_CHOICES)
    file_size = models.PositiveBigIntegerField()  # Size in bytes
    mime_type = models.CharField(max_length=100)
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'message_attachments'
        indexes = [
            models.Index(fields=['message']),
            models.Index(fields=['file_type']),
            models.Index(fields=['created_at']),
        ]
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Attachment: {self.filename}"
    
    def save(self, *args, **kwargs):
        """Override save to set file information."""
        if self.file:
            self.filename = os.path.basename(self.file.name)
            self.file_size = self.file.size
        super().save(*args, **kwargs)
    
    @property
    def human_readable_size(self):
        """Return human readable file size."""
        size = self.file_size
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} TB"


class ConversationManager(models.Manager):
    """Custom manager for Conversation model."""
    
    def get_conversations_for_user(self, user):
        """Get all conversations for a specific user."""
        return self.filter(participants=user, is_active=True)
    
    def get_conversation_between_users(self, user1, user2):
        """Get or create a direct conversation between two users."""
        conversation = self.filter(
            conversation_type='direct',
            participants=user1
        ).filter(
            participants=user2
        ).first()
        
        if conversation:
            return conversation
        
        # Create new conversation if none exists
        conversation = Conversation.objects.create(
            conversation_type='direct',
            name=f"{user1.get_full_name()} & {user2.get_full_name()}"
        )
        conversation.participants.add(user1, user2)
        return conversation


class Conversation(models.Model):
    """
    Represents a conversation between users.
    Supports both direct messages and group conversations.
    """
    CONVERSATION_TYPE_CHOICES = [
        ('direct', 'Direct Message'),
        ('group', 'Group Conversation'),
        ('channel', 'Channel'),
    ]
    
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('archived', 'Archived'),
        ('muted', 'Muted'),
        ('closed', 'Closed'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255, blank=True)
    description = models.TextField(blank=True)
    conversation_type = models.CharField(max_length=20, choices=CONVERSATION_TYPE_CHOICES, default='direct')
    participants = models.ManyToManyField(User, related_name='conversations')
    image = models.ImageField(upload_to=conversation_image_upload_path, null=True, blank=True)
    
    # Conversation Settings
    is_active = models.BooleanField(default=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    is_private = models.BooleanField(default=True)
    max_participants = models.PositiveIntegerField(default=2)
    
    # Activity Tracking
    last_message = models.ForeignKey(Message, null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    last_message_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_conversations')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Settings
    allow_file_sharing = models.BooleanField(default=True)
    allow_voice_messages = models.BooleanField(default=True)
    message_retention_days = models.PositiveIntegerField(null=True, blank=True)  # None = infinite
    
    objects = ConversationManager()
    
    class Meta:
        db_table = 'conversations'
        indexes = [
            models.Index(fields=['conversation_type']),
            models.Index(fields=['is_active']),
            models.Index(fields=['status']),
            models.Index(fields=['last_message_at']),
            models.Index(fields=['created_at']),
        ]
        ordering = ['-last_message_at']
        permissions = [
            ('can_manage_conversation', 'Can manage conversation settings'),
            ('can_add_participants', 'Can add participants'),
            ('can_remove_participants', 'Can remove participants'),
            ('can_delete_conversation', 'Can delete conversation'),
        ]
    
    def __str__(self):
        return self.name or f"Conversation {self.id}"
    
    def add_participant(self, user):
        """Add a user to the conversation."""
        if self.participants.count() >= self.max_participants:
            raise ValueError("Maximum participants reached")
        self.participants.add(user)
    
    def remove_participant(self, user):
        """Remove a user from the conversation."""
        if self.participants.count() <= 2 and self.conversation_type == 'direct':
            raise ValueError("Cannot remove participants from direct conversations")
        self.participants.remove(user)
    
    def get_participant_count(self):
        """Get the current number of participants."""
        return self.participants.count()
    
    def get_unread_count_for_user(self, user):
        """Get unread message count for a specific user."""
        return self.messages.filter(
            is_read=False,
            is_deleted=False
        ).exclude(sender=user).count()
    
    def update_last_message(self, message):
        """Update last message information."""
        self.last_message = message
        self.last_message_at = message.created_at
        self.save(update_fields=['last_message', 'last_message_at'])
    
    def archive_conversation(self):
        """Archive the conversation."""
        self.status = 'archived'
        self.is_active = False
        self.save(update_fields=['status', 'is_active'])
    
    def close_conversation(self):
        """Close the conversation permanently."""
        self.status = 'closed'
        self.is_active = False
        self.save(update_fields=['status', 'is_active'])
    
    def is_participant(self, user):
        """Check if a user is a participant in this conversation."""
        return self.participants.filter(id=user.id).exists()