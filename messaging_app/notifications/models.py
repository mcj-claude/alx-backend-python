from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.core.validators import URLValidator
import uuid


User = get_user_model()


class NotificationChannel(models.Model):
    """
    Represents different notification channels (email, push, SMS, etc.).
    """
    CHANNEL_TYPES = [
        ('email', 'Email'),
        ('push', 'Push Notification'),
        ('sms', 'SMS'),
        ('webhook', 'Webhook'),
        ('slack', 'Slack'),
        ('discord', 'Discord'),
        ('teams', 'Microsoft Teams'),
    ]
    
    name = models.CharField(max_length=100, unique=True)
    channel_type = models.CharField(max_length=20, choices=CHANNEL_TYPES)
    is_active = models.BooleanField(default=True)
    config = models.JSONField(default=dict, blank=True)  # Channel-specific configuration
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'notification_channels'
        ordering = ['name']
    
    def __str__(self):
        return f"{self.name} ({self.get_channel_type_display()})"


class NotificationCategory(models.Model):
    """
    Categories for organizing notifications.
    """
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    color = models.CharField(max_length=7, default='#007bff')  # Hex color code
    icon = models.CharField(max_length=50, default='bell')  # Icon name
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'notification_categories'
        ordering = ['sort_order', 'name']
        verbose_name_plural = 'Notification Categories'
    
    def __str__(self):
        return self.name


class NotificationManager(models.Manager):
    """Custom manager for Notification model."""
    
    def unread(self, user):
        """Get unread notifications for a user."""
        return self.filter(user=user, is_read=False)
    
    def unread_count(self, user):
        """Get count of unread notifications for a user."""
        return self.unread(user).count()
    
    def mark_all_as_read(self, user):
        """Mark all notifications as read for a user."""
        return self.filter(user=user, is_read=False).update(
            is_read=True, read_at=timezone.now()
        )


class Notification(models.Model):
    """
    Main notification model for the messaging platform.
    Supports multiple notification types, channels, and delivery methods.
    """
    PRIORITY_CHOICES = [
        ('low', 'Low'),
        ('normal', 'Normal'),
        ('high', 'High'),
        ('urgent', 'Urgent'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('sent', 'Sent'),
        ('delivered', 'Delivered'),
        ('failed', 'Failed'),
        ('read', 'Read'),
        ('archived', 'Archived'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    sender = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='sent_notifications')
    
    # Content
    title = models.CharField(max_length=255)
    message = models.TextField()
    category = models.ForeignKey(NotificationCategory, on_delete=models.CASCADE, related_name='notifications')
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='normal')
    
    # Related Objects
    related_object_type = models.CharField(max_length=100, blank=True)  # e.g., 'message', 'conversation'
    related_object_id = models.UUIDField(null=True, blank=True)
    
    # Notification Data
    action_url = models.URLField(blank=True, validators=[URLValidator])
    image_url = models.URLField(blank=True)
    extra_data = models.JSONField(default=dict, blank=True)
    
    # Status and Delivery
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    channels = models.ManyToManyField(NotificationChannel, related_name='notifications')
    
    # Timestamps
    scheduled_at = models.DateTimeField(null=True, blank=True)  # For scheduled notifications
    sent_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)  # For temporary notifications
    
    # Flags
    is_read = models.BooleanField(default=False)
    is_archived = models.BooleanField(default=False)
    is_clicked = models.BooleanField(default=False)
    clicked_at = models.DateTimeField(null=True, blank=True)
    is_dismissed = models.BooleanField(default=False)
    dismissed_at = models.DateTimeField(null=True, blank=True)
    
    objects = NotificationManager()
    
    class Meta:
        db_table = 'notifications'
        indexes = [
            models.Index(fields=['user']),
            models.Index(fields=['user', 'is_read']),
            models.Index(fields=['user', 'status']),
            models.Index(fields=['category']),
            models.Index(fields=['priority']),
            models.Index(fields=['created_at']),
            models.Index(fields=['scheduled_at']),
            models.Index(fields=['expires_at']),
            models.Index(fields=['user', 'created_at']),
        ]
        ordering = ['-created_at']
        permissions = [
            ('can_send_notifications', 'Can send notifications to users'),
            ('can_manage_categories', 'Can manage notification categories'),
            ('can_view_all_notifications', 'Can view all notifications'),
        ]
    
    def __str__(self):
        return f"{self.title} - {self.user.email}"
    
    def mark_as_read(self):
        """Mark notification as read."""
        if not self.is_read:
            self.is_read = True
            self.read_at = timezone.now()
            self.status = 'read'
            self.save(update_fields=['is_read', 'read_at', 'status'])
    
    def mark_as_clicked(self):
        """Mark notification as clicked."""
        if not self.is_clicked:
            self.is_clicked = True
            self.clicked_at = timezone.now()
            self.save(update_fields=['is_clicked', 'clicked_at'])
    
    def archive(self):
        """Archive the notification."""
        self.is_archived = True
        self.status = 'archived'
        self.save(update_fields=['is_archived', 'status'])
    
    def dismiss(self):
        """Dismiss the notification."""
        self.is_dismissed = True
        self.dismissed_at = timezone.now()
        self.save(update_fields=['is_dismissed', 'dismissed_at'])
    
    def mark_as_sent(self):
        """Mark notification as sent."""
        self.status = 'sent'
        self.sent_at = timezone.now()
        self.save(update_fields=['status', 'sent_at'])
    
    def mark_as_delivered(self):
        """Mark notification as delivered."""
        self.status = 'delivered'
        self.delivered_at = timezone.now()
        self.save(update_fields=['status', 'delivered_at'])
    
    def is_expired(self):
        """Check if notification has expired."""
        return self.expires_at and timezone.now() > self.expires_at
    
    def should_deliver(self):
        """Check if notification should be delivered."""
        if self.is_expired():
            return False
        if self.is_archived or self.is_dismissed:
            return False
        return self.status in ['pending', 'scheduled']
    
    def get_related_object(self):
        """Get the related object if it exists."""
        if self.related_object_type and self.related_object_id:
            # This would need to be implemented based on your app structure
            # For now, just return None
            return None
        return None


class NotificationPreference(models.Model):
    """
    User preferences for different types of notifications and channels.
    """
    FREQUENCY_CHOICES = [
        ('immediate', 'Immediate'),
        ('hourly', 'Hourly Digest'),
        ('daily', 'Daily Digest'),
        ('weekly', 'Weekly Digest'),
        ('never', 'Never'),
    ]
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='notification_preferences')
    category = models.ForeignKey(NotificationCategory, on_delete=models.CASCADE, related_name='user_preferences')
    
    # Channel Preferences
    email_enabled = models.BooleanField(default=True)
    push_enabled = models.BooleanField(default=True)
    sms_enabled = models.BooleanField(default=False)
    
    # Frequency Preferences
    frequency = models.CharField(max_length=20, choices=FREQUENCY_CHOICES, default='immediate')
    
    # Quiet Hours
    quiet_hours_enabled = models.BooleanField(default=False)
    quiet_hours_start = models.TimeField(null=True, blank=True)
    quiet_hours_end = models.TimeField(null=True, blank=True)
    
    # Settings
    is_enabled = models.BooleanField(default=True)
    do_not_disturb_until = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'notification_preferences'
        unique_together = ('user', 'category')
        ordering = ['category__name']
    
    def __str__(self):
        return f"{self.user.email} - {self.category.name}"
    
    def is_quiet_time(self):
        """Check if current time is within quiet hours."""
        if not self.quiet_hours_enabled or not self.quiet_hours_start or not self.quiet_hours_end:
            return False
        
        now = timezone.localtime(timezone.now()).time()
        start = self.quiet_hours_start
        end = self.quiet_hours_end
        
        if start <= end:
            return start <= now <= end
        else:  # Quiet hours cross midnight
            return now >= start or now <= end
    
    def should_receive_notification(self):
        """Check if user should receive notifications for this category."""
        if not self.is_enabled:
            return False
        
        if self.do_not_disturb_until and timezone.now() < self.do_not_disturb_until:
            return False
        
        if self.is_quiet_time():
            return False
        
        return True


class EmailNotification(models.Model):
    """
    Email-specific notification tracking.
    """
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('sent', 'Sent'),
        ('delivered', 'Delivered'),
        ('opened', 'Opened'),
        ('clicked', 'Clicked'),
        ('bounced', 'Bounced'),
        ('failed', 'Failed'),
        ('unsubscribed', 'Unsubscribed'),
    ]
    
    notification = models.OneToOneField(Notification, on_delete=models.CASCADE, related_name='email_notification')
    to_email = models.EmailField()
    from_email = models.EmailField(default='noreply@messagingapp.com')
    subject = models.CharField(max_length=255)
    html_content = models.TextField()
    text_content = models.TextField()
    
    # Email tracking
    message_id = models.CharField(max_length=255, blank=True)  # Email service message ID
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # Tracking data
    opened_at = models.DateTimeField(null=True, blank=True)
    clicked_at = models.DateTimeField(null=True, blank=True)
    bounced_at = models.DateTimeField(null=True, blank=True)
    bounce_type = models.CharField(max_length=50, blank=True)  # hard, soft, etc.
    
    # Metadata
    retry_count = models.PositiveIntegerField(default=0)
    error_message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'email_notifications'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Email: {self.subject} to {self.to_email}"
    
    def mark_as_opened(self):
        """Mark email as opened."""
        self.opened_at = timezone.now()
        self.status = 'opened'
        self.save(update_fields=['opened_at', 'status'])
    
    def mark_as_clicked(self):
        """Mark email as clicked."""
        self.clicked_at = timezone.now()
        self.status = 'clicked'
        self.save(update_fields=['clicked_at', 'status'])
    
    def mark_as_bounced(self, bounce_type='unknown'):
        """Mark email as bounced."""
        self.bounced_at = timezone.now()
        self.bounce_type = bounce_type
        self.status = 'bounced'
        self.save(update_fields=['bounced_at', 'bounce_type', 'status'])


class PushNotification(models.Model):
    """
    Push notification tracking for mobile and web.
    """
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('sent', 'Sent'),
        ('delivered', 'Delivered'),
        ('failed', 'Failed'),
        ('clicked', 'Clicked'),
    ]
    
    notification = models.OneToOneField(Notification, on_delete=models.CASCADE, related_name='push_notification')
    
    # Push notification data
    title = models.CharField(max_length=255)
    body = models.TextField()
    icon = models.URLField(blank=True)
    image = models.URLField(blank=True)
    sound = models.CharField(max_length=100, blank=True)
    badge = models.PositiveIntegerField(null=True, blank=True)
    
    # Device and platform
    device_token = models.CharField(max_length=500, blank=True)  # FCM/APNS token
    platform = models.CharField(max_length=50, blank=True)  # ios, android, web
    
    # Data payload (additional data for the app)
    data = models.JSONField(default=dict, blank=True)
    
    # Tracking
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    message_id = models.CharField(max_length=255, blank=True)  # Push service message ID
    
    # Timestamps
    sent_at = models.DateTimeField(null=True, blank=True)
    clicked_at = models.DateTimeField(null=True, blank=True)
    failed_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'push_notifications'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Push: {self.title} to {self.platform}"
    
    def mark_as_sent(self):
        """Mark push notification as sent."""
        self.status = 'sent'
        self.sent_at = timezone.now()
        self.save(update_fields=['status', 'sent_at'])
    
    def mark_as_clicked(self):
        """Mark push notification as clicked."""
        self.status = 'clicked'
        self.clicked_at = timezone.now()
        self.save(update_fields=['status', 'clicked_at'])
    
    def mark_as_failed(self, error_message=''):
        """Mark push notification as failed."""
        self.status = 'failed'
        self.failed_at = timezone.now()
        self.error_message = error_message
        self.save(update_fields=['status', 'failed_at', 'error_message'])


class WebhookNotification(models.Model):
    """
    Webhook notifications for external integrations.
    """
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('sent', 'Sent'),
        ('delivered', 'Delivered'),
        ('failed', 'Failed'),
        ('retried', 'Retried'),
    ]
    
    notification = models.OneToOneField(Notification, on_delete=models.CASCADE, related_name='webhook_notification')
    
    # Webhook configuration
    url = models.URLField()
    method = models.CharField(max_length=10, default='POST')
    headers = models.JSONField(default=dict, blank=True)
    
    # Payload
    payload = models.JSONField(default=dict)
    
    # Response tracking
    status_code = models.PositiveIntegerField(null=True, blank=True)
    response_body = models.TextField(blank=True)
    response_headers = models.JSONField(default=dict, blank=True)
    
    # Status and retry
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    retry_count = models.PositiveIntegerField(default=0)
    max_retries = models.PositiveIntegerField(default=3)
    next_retry_at = models.DateTimeField(null=True, blank=True)
    
    # Timestamps
    sent_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    failed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'webhook_notifications'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Webhook: {self.method} {self.url}"
    
    def can_retry(self):
        """Check if webhook can be retried."""
        return self.retry_count < self.max_retries and self.status in ['failed', 'retried']
    
    def mark_as_delivered(self, status_code, response_body='', response_headers=None):
        """Mark webhook as successfully delivered."""
        self.status = 'delivered'
        self.status_code = status_code
        self.response_body = response_body
        self.response_headers = response_headers or {}
        self.delivered_at = timezone.now()
        self.save(update_fields=[
            'status', 'status_code', 'response_body', 'response_headers', 'delivered_at'
        ])
    
    def mark_as_failed(self, status_code=None, response_body=''):
        """Mark webhook as failed."""
        self.status = 'failed' if not self.can_retry() else 'retried'
        self.status_code = status_code
        self.response_body = response_body
        self.failed_at = timezone.now()
        
        if self.can_retry():
            self.retry_count += 1
            # Schedule retry in 5 minutes
            from datetime import timedelta
            self.next_retry_at = timezone.now() + timedelta(minutes=5)
        
        self.save(update_fields=[
            'status', 'status_code', 'response_body', 'failed_at', 
            'retry_count', 'next_retry_at'
        ])