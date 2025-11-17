from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from .models import (
    NotificationChannel, NotificationCategory, Notification, 
    NotificationPreference, EmailNotification, PushNotification, 
    WebhookNotification
)


@admin.register(NotificationChannel)
class NotificationChannelAdmin(admin.ModelAdmin):
    """Admin interface for NotificationChannel model."""
    
    list_display = ('name', 'channel_type', 'is_active', 'created_at')
    list_filter = ('channel_type', 'is_active', 'created_at')
    search_fields = ('name',)
    readonly_fields = ('created_at', 'updated_at')
    
    fieldsets = (
        (None, {
            'fields': ('name', 'channel_type', 'is_active')
        }),
        ('Configuration', {
            'fields': ('config',)
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at')
        }),
    )


@admin.register(NotificationCategory)
class NotificationCategoryAdmin(admin.ModelAdmin):
    """Admin interface for NotificationCategory model."""
    
    list_display = ('name', 'sort_order', 'is_active', 'created_at')
    list_filter = ('is_active', 'created_at')
    search_fields = ('name', 'description')
    readonly_fields = ('created_at',)
    
    fieldsets = (
        (None, {
            'fields': ('name', 'description', 'sort_order', 'is_active')
        }),
        ('Appearance', {
            'fields': ('color', 'icon')
        }),
        ('Metadata', {
            'fields': ('created_at',)
        }),
    )


class EmailNotificationInline(admin.TabularInline):
    """Inline admin for email notifications."""
    model = EmailNotification
    extra = 0
    readonly_fields = ('to_email', 'subject', 'status', 'sent_at', 'opened_at', 'clicked_at')


class PushNotificationInline(admin.TabularInline):
    """Inline admin for push notifications."""
    model = PushNotification
    extra = 0
    readonly_fields = ('title', 'platform', 'status', 'sent_at', 'clicked_at')


class WebhookNotificationInline(admin.TabularInline):
    """Inline admin for webhook notifications."""
    model = WebhookNotification
    extra = 0
    readonly_fields = ('url', 'method', 'status', 'status_code', 'sent_at')


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    """Admin interface for Notification model."""
    
    list_display = (
        'title', 'user_email', 'category', 'priority', 'status', 
        'is_read', 'is_archived', 'scheduled_at', 'created_at'
    )
    list_filter = (
        'priority', 'status', 'category', 'is_read', 'is_archived', 
        'is_clicked', 'is_dismissed', 'created_at', 'scheduled_at'
    )
    search_fields = ('title', 'message', 'user__email', 'user__username')
    readonly_fields = (
        'id', 'read_at', 'clicked_at', 'dismissed_at', 'sent_at', 
        'delivered_at', 'created_at'
    )
    
    fieldsets = (
        (None, {
            'fields': ('id', 'user', 'sender', 'title', 'message')
        }),
        ('Categorization', {
            'fields': ('category', 'priority')
        }),
        ('Related Object', {
            'fields': ('related_object_type', 'related_object_id')
        }),
        ('Content & Links', {
            'fields': ('action_url', 'image_url', 'extra_data')
        }),
        ('Status', {
            'fields': ('status', 'channels', 'scheduled_at')
        }),
        ('Flags', {
            'fields': ('is_read', 'is_archived', 'is_clicked', 'clicked_at', 
                      'is_dismissed', 'dismissed_at')
        }),
        ('Delivery', {
            'fields': ('sent_at', 'delivered_at', 'expires_at')
        }),
        ('Metadata', {
            'fields': ('created_at',)
        }),
    )
    
    filter_horizontal = ('channels',)
    
    def user_email(self, obj):
        """Display user email."""
        return obj.user.email
    user_email.short_description = 'User'
    
    def get_queryset(self, request):
        """Optimize queryset with select_related."""
        qs = super().get_queryset(request)
        return qs.select_related('user', 'sender', 'category')
    
    actions = ['mark_as_read', 'mark_as_unread', 'archive_notifications', 'delete_notifications']
    
    def mark_as_read(self, request, queryset):
        """Action to mark notifications as read."""
        updated = 0
        for notification in queryset:
            notification.mark_as_read()
            updated += 1
        self.message_user(request, f'{updated} notifications were marked as read.')
    mark_as_read.short_description = "Mark selected notifications as read"
    
    def mark_as_unread(self, request, queryset):
        """Action to mark notifications as unread."""
        updated = queryset.update(is_read=False, read_at=None, status='pending')
        self.message_user(request, f'{updated} notifications were marked as unread.')
    mark_as_unread.short_description = "Mark selected notifications as unread"
    
    def archive_notifications(self, request, queryset):
        """Action to archive notifications."""
        updated = 0
        for notification in queryset:
            notification.archive()
            updated += 1
        self.message_user(request, f'{updated} notifications were archived.')
    archive_notifications.short_description = "Archive selected notifications"
    
    def delete_notifications(self, request, queryset):
        """Action to delete notifications."""
        count = queryset.count()
        queryset.delete()
        self.message_user(request, f'{count} notifications were deleted.')
    delete_notifications.short_description = "Delete selected notifications"


@admin.register(NotificationPreference)
class NotificationPreferenceAdmin(admin.ModelAdmin):
    """Admin interface for NotificationPreference model."""
    
    list_display = ('user_email', 'category', 'frequency', 'is_enabled', 'quiet_hours_enabled')
    list_filter = ('frequency', 'is_enabled', 'quiet_hours_enabled', 'email_enabled', 'push_enabled', 'sms_enabled')
    search_fields = ('user__email', 'user__username', 'category__name')
    readonly_fields = ('created_at', 'updated_at')
    
    fieldsets = (
        (None, {
            'fields': ('user', 'category')
        }),
        ('Channel Preferences', {
            'fields': ('email_enabled', 'push_enabled', 'sms_enabled')
        }),
        ('Frequency', {
            'fields': ('frequency',)
        }),
        ('Quiet Hours', {
            'fields': ('quiet_hours_enabled', 'quiet_hours_start', 'quiet_hours_end')
        }),
        ('Settings', {
            'fields': ('is_enabled', 'do_not_disturb_until')
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at')
        }),
    )
    
    def user_email(self, obj):
        """Display user email."""
        return obj.user.email
    user_email.short_description = 'User'


@admin.register(EmailNotification)
class EmailNotificationAdmin(admin.ModelAdmin):
    """Admin interface for EmailNotification model."""
    
    list_display = (
        'subject', 'to_email', 'status', 'opened', 'clicked', 
        'bounced', 'retry_count', 'created_at'
    )
    list_filter = ('status', 'bounce_type', 'retry_count', 'created_at')
    search_fields = ('subject', 'to_email', 'message_id')
    readonly_fields = (
        'created_at', 'updated_at', 'opened_at', 'clicked_at', 
        'bounced_at'
    )
    
    fieldsets = (
        (None, {
            'fields': ('notification', 'to_email', 'from_email', 'subject')
        }),
        ('Content', {
            'fields': ('html_content', 'text_content')
        }),
        ('Tracking', {
            'fields': ('message_id', 'status', 'opened_at', 'clicked_at', 'bounced_at')
        }),
        ('Bounce Information', {
            'fields': ('bounce_type',)
        }),
        ('Retry & Error', {
            'fields': ('retry_count', 'error_message')
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at')
        }),
    )
    
    def opened(self, obj):
        """Show if email was opened."""
        if obj.opened_at:
            return format_html('<span style="color: green;">✓</span>')
        return format_html('<span style="color: red;">✗</span>')
    opened.boolean = True
    opened.short_description = 'Opened'
    
    def clicked(self, obj):
        """Show if email was clicked."""
        if obj.clicked_at:
            return format_html('<span style="color: green;">✓</span>')
        return format_html('<span style="color: red;">✗</span>')
    clicked.boolean = True
    clicked.short_description = 'Clicked'
    
    def bounced(self, obj):
        """Show if email bounced."""
        if obj.bounced_at:
            return format_html('<span style="color: red;">Bounced</span>')
        return format_html('<span style="color: green;">OK</span>')
    bounced.boolean = True
    bounced.short_description = 'Bounced'


@admin.register(PushNotification)
class PushNotificationAdmin(admin.ModelAdmin):
    """Admin interface for PushNotification model."""
    
    list_display = ('title', 'platform', 'device_token_preview', 'status', 'clicked', 'created_at')
    list_filter = ('platform', 'status', 'created_at')
    search_fields = ('title', 'body', 'device_token')
    readonly_fields = ('created_at', 'updated_at', 'sent_at', 'clicked_at', 'failed_at')
    
    fieldsets = (
        (None, {
            'fields': ('notification', 'title', 'body')
        }),
        ('Device Information', {
            'fields': ('device_token', 'platform')
        }),
        ('Display Options', {
            'fields': ('icon', 'image', 'sound', 'badge')
        }),
        ('Data Payload', {
            'fields': ('data',)
        }),
        ('Status', {
            'fields': ('status', 'message_id', 'sent_at', 'clicked_at', 'failed_at')
        }),
        ('Error Information', {
            'fields': ('error_message',)
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at')
        }),
    )
    
    def device_token_preview(self, obj):
        """Display preview of device token."""
        if obj.device_token:
            return obj.device_token[:20] + '...'
        return 'No token'
    device_token_preview.short_description = 'Device Token'
    
    def clicked(self, obj):
        """Show if push notification was clicked."""
        if obj.clicked_at:
            return format_html('<span style="color: green;">✓</span>')
        return format_html('<span style="color: red;">✗</span>')
    clicked.boolean = True
    clicked.short_description = 'Clicked'


@admin.register(WebhookNotification)
class WebhookNotificationAdmin(admin.ModelAdmin):
    """Admin interface for WebhookNotification model."""
    
    list_display = (
        'method', 'url_preview', 'status', 'status_code', 'retry_count', 'created_at'
    )
    list_filter = ('method', 'status', 'retry_count', 'created_at')
    search_fields = ('url', 'payload', 'response_body')
    readonly_fields = (
        'created_at', 'updated_at', 'sent_at', 'delivered_at', 'failed_at'
    )
    
    fieldsets = (
        (None, {
            'fields': ('notification', 'url', 'method')
        }),
        ('Request', {
            'fields': ('headers', 'payload')
        }),
        ('Response', {
            'fields': ('status_code', 'response_body', 'response_headers')
        }),
        ('Status & Retry', {
            'fields': ('status', 'sent_at', 'delivered_at', 'failed_at')
        }),
        ('Retry Configuration', {
            'fields': ('retry_count', 'max_retries', 'next_retry_at')
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at')
        }),
    )
    
    def url_preview(self, obj):
        """Display preview of URL."""
        return obj.url[:50] + '...' if len(obj.url) > 50 else obj.url
    url_preview.short_description = 'URL'
    
    actions = ['retry_failed_webhooks']
    
    def retry_failed_webhooks(self, request, queryset):
        """Action to retry failed webhooks."""
        updated = 0
        for webhook in queryset:
            if webhook.can_retry():
                webhook.status = 'pending'
                webhook.next_retry_at = None
                webhook.save(update_fields=['status', 'next_retry_at'])
                updated += 1
        self.message_user(request, f'{updated} webhooks were queued for retry.')
    retry_failed_webhooks.short_description = "Retry failed webhooks"