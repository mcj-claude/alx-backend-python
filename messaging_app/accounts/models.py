from django.contrib.auth.models import AbstractUser
from django.db import models
from django.core.validators import validate_email
from django.utils import timezone
import uuid


class User(AbstractUser):
    """
    Custom User model with extended fields and advanced features.
    Implements authentication with email support and additional profile fields.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True, validators=[validate_email])
    phone_number = models.CharField(max_length=20, blank=True, null=True)
    profile_picture = models.ImageField(upload_to='profile_pictures/', blank=True, null=True)
    
    # Profile Information
    first_name = models.CharField(max_length=30, blank=True)
    last_name = models.CharField(max_length=150, blank=True)
    bio = models.TextField(max_length=500, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    
    # Privacy Settings
    is_profile_public = models.BooleanField(default=True)
    is_phone_visible = models.BooleanField(default=False)
    show_online_status = models.BooleanField(default=True)
    
    # Account Status
    is_active = models.BooleanField(default=True)
    is_verified = models.BooleanField(default=False)
    is_suspended = models.BooleanField(default=False)
    last_login_ip = models.GenericIPAddressField(null=True, blank=True)
    
    # Activity Tracking
    last_seen = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    password_changed_at = models.DateTimeField(default=timezone.now)
    
    # Preferences
    preferred_language = models.CharField(max_length=10, default='en')
    timezone = models.CharField(max_length=50, default='UTC')
    email_notifications = models.BooleanField(default=True)
    push_notifications = models.BooleanField(default=True)
    
    # Security Settings
    two_factor_enabled = models.BooleanField(default=False)
    two_factor_secret = models.CharField(max_length=32, blank=True)
    login_attempts = models.IntegerField(default=0)
    locked_until = models.DateTimeField(null=True, blank=True)
    
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']
    
    class Meta:
        db_table = 'users'
        indexes = [
            models.Index(fields=['email']),
            models.Index(fields=['username']),
            models.Index(fields=['is_active']),
            models.Index(fields=['last_seen']),
            models.Index(fields=['created_at']),
        ]
        ordering = ['-created_at']
        verbose_name = 'User'
        verbose_name_plural = 'Users'
    
    def __str__(self):
        return f"{self.get_full_name()} ({self.email})"
    
    def get_full_name(self):
        """Return the user's full name."""
        full_name = f"{self.first_name} {self.last_name}"
        return full_name.strip() or self.username
    
    def get_short_name(self):
        """Return the user's short name."""
        return self.first_name or self.username
    
    @property
    def display_name(self):
        """Return a display name for the user."""
        return self.get_full_name() or self.username
    
    def is_online(self):
        """Check if user is currently online."""
        if not self.show_online_status:
            return False
        return (timezone.now() - self.last_seen).seconds < 300  # 5 minutes
    
    def is_locked(self):
        """Check if user account is locked."""
        if self.locked_until and self.locked_until > timezone.now():
            return True
        return False
    
    def get_unread_notifications_count(self):
        """Get count of unread notifications for this user."""
        from notifications.models import Notification
        return Notification.objects.filter(user=self, is_read=False).count()
    
    def get_unread_messages_count(self):
        """Get count of unread messages for this user."""
        from messaging.models import Message
        return Message.objects.filter(
            conversation__participants=self,
            is_read=False
        ).exclude(sender=self).count()
    
    def update_last_seen(self):
        """Update last seen timestamp."""
        self.last_seen = timezone.now()
        self.save(update_fields=['last_seen'])
    
    def save(self, *args, **kwargs):
        """Override save to handle password changes."""
        if self.pk and hasattr(self, '_password_changed'):
            self.password_changed_at = timezone.now()
        super().save(*args, **kwargs)
    
    def set_password(self, raw_password):
        """Set password and track when it was changed."""
        super().set_password(raw_password)
        self._password_changed = True
    
    def check_password(self, raw_password):
        """Check password with attempt tracking."""
        result = super().check_password(raw_password)
        if not result:
            self.login_attempts += 1
            if self.login_attempts >= 5:
                from django.utils import timezone as tz
                self.locked_until = tz.now() + timezone.timedelta(minutes=30)
            self.save(update_fields=['login_attempts', 'locked_until'])
        else:
            # Reset on successful login
            self.login_attempts = 0
            self.locked_until = None
            self.last_login_ip = None
            self.save(update_fields=['login_attempts', 'locked_until', 'last_login_ip'])
        return result