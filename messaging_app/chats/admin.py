"""
Django Admin Configuration for Messaging Platform Models

Provides admin interfaces for managing users, conversations, and messages
with proper filtering, search functionality, and bulk operations.
"""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.html import format_html
from .models import User, Conversation, Message, ConversationParticipant


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """
    Admin interface for User model with custom fields and functionality.
    
    Provides comprehensive user management with role-based filtering,
    search capabilities, and bulk operations.
    """
    
    list_display = (
        'display_name', 'email', 'phone_number', 'role', 
        'is_active', 'is_staff', 'created_at'
    )
    list_filter = (
        'role', 'is_active', 'is_staff', 'is_superuser', 'created_at'
    )
    search_fields = (
        'email', 'first_name', 'last_name', 'phone_number'
    )
    readonly_fields = (
        'user_id', 'created_at', 'last_login', 'date_joined'
    )
    
    fieldsets = (
        ('Authentication', {
            'fields': ('email', 'user_id')
        }),
        ('Personal Information', {
            'fields': ('first_name', 'last_name', 'phone_number')
        }),
        ('Role & Permissions', {
            'fields': ('role', 'is_active', 'is_staff', 'is_superuser', 
                      'groups', 'user_permissions')
        }),
        ('Important Dates', {
            'fields': ('created_at', 'last_login', 'date_joined')
        }),
    )
    
    filter_horizontal = ('groups', 'user_permissions')
    
    def get_queryset(self, request):
        """Optimize queryset with select_related."""
        qs = super().get_queryset(request)
        return qs.select_related()
    
    actions = ['activate_users', 'deactivate_users', 'make_hosts', 'make_admins']
    
    def activate_users(self, request, queryset):
        """Activate selected users."""
        updated = queryset.update(is_active=True)
        self.message_user(request, f'{updated} users were activated.')
    activate_users.short_description = "Activate selected users"
    
    def deactivate_users(self, request, queryset):
        """Deactivate selected users."""
        updated = queryset.update(is_active=False)
        self.message_user(request, f'{updated} users were deactivated.')
    deactivate_users.short_description = "Deactivate selected users"
    
    def make_hosts(self, request, queryset):
        """Change selected users to host role."""
        updated = queryset.update(role='host')
        self.message_user(request, f'{updated} users were changed to host role.')
    make_hosts.short_description = "Change selected users to host role"
    
    def make_admins(self, request, queryset):
        """Change selected users to admin role."""
        updated = queryset.update(role='admin')
        self.message_user(request, f'{updated} users were changed to admin role.')
    make_admins.short_description = "Change selected users to admin role"


class MessageInline(admin.TabularInline):
    """Inline admin for messages within conversations."""
    model = Message
    extra = 0
    readonly_fields = ('sender', 'sent_at', 'message_id')
    fields = ('sender', 'message_body', 'sent_at')


class ConversationParticipantInline(admin.TabularInline):
    """Inline admin for conversation participants."""
    model = ConversationParticipant
    extra = 0
    readonly_fields = ('joined_at',)
    fields = ('user', 'is_admin')


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    """
    Admin interface for Conversation model with participant management.
    
    Provides conversation management with participant oversight and
    message preview capabilities.
    """
    
    list_display = (
        'conversation_id', 'title', 'participant_count', 
        'message_count', 'created_at', 'is_active'
    )
    list_filter = ('is_active', 'created_at')
    search_fields = ('conversation_id', 'title')
    readonly_fields = ('conversation_id', 'created_at', 'participant_count', 'message_count')
    
    fieldsets = (
        ('Conversation Information', {
            'fields': ('conversation_id', 'title', 'is_active')
        }),
        ('Statistics', {
            'fields': ('participant_count', 'message_count', 'created_at'),
            'classes': ('collapse',)
        }),
    )
    
    inlines = [ConversationParticipantInline, MessageInline]
    
    def participant_count(self, obj):
        """Display participant count."""
        return obj.participants.count()
    participant_count.short_description = 'Participants'
    
    def message_count(self, obj):
        """Display message count."""
        return obj.messages.count()
    message_count.short_description = 'Messages'
    
    actions = ['archive_conversations', 'activate_conversations']
    
    def archive_conversations(self, request, queryset):
        """Archive selected conversations."""
        updated = queryset.update(is_active=False)
        self.message_user(request, f'{updated} conversations were archived.')
    archive_conversations.short_description = "Archive selected conversations"
    
    def activate_conversations(self, request, queryset):
        """Activate selected conversations."""
        updated = queryset.update(is_active=True)
        self.message_user(request, f'{updated} conversations were activated.')
    activate_conversations.short_description = "Activate selected conversations"


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    """
    Admin interface for Message model with conversation threading support.
    
    Provides message management with conversation and sender filtering,
    plus message content search capabilities.
    """
    
    list_display = (
        'message_preview', 'sender', 'conversation', 
        'sent_at', 'is_deleted', 'reply_depth'
    )
    list_filter = ('is_deleted', 'sent_at', 'conversation')
    search_fields = ('message_body', 'sender__email', 'sender__first_name')
    readonly_fields = ('message_id', 'sent_at', 'deleted_at')
    
    fieldsets = (
        ('Message Information', {
            'fields': ('message_id', 'conversation', 'sender')
        }),
        ('Content', {
            'fields': ('message_body', 'reply_to')
        }),
        ('Metadata', {
            'fields': ('sent_at', 'is_deleted', 'deleted_at')
        }),
    )
    
    def message_preview(self, obj):
        """Display preview of message content."""
        preview = obj.message_body[:50]
        if len(obj.message_body) > 50:
            preview += "..."
        return preview
    message_preview.short_description = 'Message Preview'
    
    def reply_depth(self, obj):
        """Display reply thread depth."""
        return obj.get_thread_depth()
    reply_depth.short_description = 'Reply Depth'
    
    actions = ['delete_messages', 'restore_messages']
    
    def delete_messages(self, request, queryset):
        """Soft delete selected messages."""
        for message in queryset:
            message.soft_delete()
        updated = queryset.count()
        self.message_user(request, f'{updated} messages were deleted.')
    delete_messages.short_description = "Soft delete selected messages"
    
    def restore_messages(self, request, queryset):
        """Restore selected messages."""
        updated = 0
        for message in queryset:
            if message.is_deleted:
                message.is_deleted = False
                message.deleted_at = None
                message.save(update_fields=['is_deleted', 'deleted_at'])
                updated += 1
        self.message_user(request, f'{updated} messages were restored.')
    restore_messages.short_description = "Restore selected messages"


@admin.register(ConversationParticipant)
class ConversationParticipantAdmin(admin.ModelAdmin):
    """
    Admin interface for ConversationParticipant through table.
    
    Provides management of user participation in conversations
    with admin privilege assignment capabilities.
    """
    
    list_display = (
        'user', 'conversation', 'joined_at', 'is_admin', 'last_read_at'
    )
    list_filter = ('is_admin', 'joined_at')
    search_fields = (
        'user__email', 'user__first_name', 'user__last_name',
        'conversation__conversation_id'
    )
    readonly_fields = ('joined_at',)
    
    fieldsets = (
        ('Participation Details', {
            'fields': ('conversation', 'user', 'is_admin')
        }),
        ('Read Status', {
            'fields': ('last_read_at', 'joined_at')
        }),
    )
    
    actions = ['grant_admin_privileges', 'revoke_admin_privileges']
    
    def grant_admin_privileges(self, request, queryset):
        """Grant admin privileges to selected participants."""
        updated = queryset.update(is_admin=True)
        self.message_user(request, f'{updated} participants were granted admin privileges.')
    grant_admin_privileges.short_description = "Grant admin privileges"
    
    def revoke_admin_privileges(self, request, queryset):
        """Revoke admin privileges from selected participants."""
        updated = queryset.update(is_admin=False)
        self.message_user(request, f'{updated} participants had admin privileges revoked.')
    revoke_admin_privileges.short_description = "Revoke admin privileges"