from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from .models import Conversation, Message, MessageThread, MessageAttachment


class MessageInline(admin.TabularInline):
    """Inline admin for messages in conversations."""
    model = Message
    extra = 0
    readonly_fields = ('sender', 'message_type', 'created_at', 'is_read', 'is_delivered')
    fields = ('sender', 'content', 'message_type', 'is_read', 'is_delivered', 'created_at')


class MessageAttachmentInline(admin.TabularInline):
    """Inline admin for message attachments."""
    model = MessageAttachment
    extra = 0
    readonly_fields = ('filename', 'file_type', 'file_size', 'human_readable_size', 'created_at')


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    """Admin interface for Conversation model."""
    
    list_display = (
        'name', 'conversation_type', 'participant_count', 'last_message_preview', 
        'status', 'is_active', 'created_at'
    )
    list_filter = (
        'conversation_type', 'status', 'is_active', 'is_private', 
        'created_at', 'updated_at'
    )
    search_fields = ('name', 'description', 'participants__email', 'participants__username')
    readonly_fields = ('id', 'created_at', 'updated_at', 'last_message_at')
    
    fieldsets = (
        (None, {
            'fields': ('id', 'name', 'description', 'conversation_type')
        }),
        ('Participants', {
            'fields': ('participants', 'created_by', 'max_participants')
        }),
        ('Settings', {
            'fields': ('is_active', 'status', 'is_private', 'allow_file_sharing', 
                      'allow_voice_messages', 'message_retention_days')
        }),
        ('Image & Media', {
            'fields': ('image',)
        }),
        ('Activity', {
            'fields': ('last_message', 'last_message_at', 'created_at', 'updated_at')
        }),
    )
    
    filter_horizontal = ('participants',)
    
    def participant_count(self, obj):
        """Display participant count."""
        return obj.participants.count()
    participant_count.short_description = 'Participants'
    
    def last_message_preview(self, obj):
        """Display preview of last message."""
        if obj.last_message:
            content = obj.last_message.content[:50]
            if len(obj.last_message.content) > 50:
                content += '...'
            return content
        return 'No messages'
    last_message_preview.short_description = 'Last Message'
    
    def get_queryset(self, request):
        """Optimize queryset with select_related."""
        qs = super().get_queryset(request)
        return qs.select_related('last_message', 'created_by').prefetch_related('participants')
    
    actions = ['archive_conversations', 'close_conversations', 'activate_conversations']
    
    def archive_conversations(self, request, queryset):
        """Action to archive selected conversations."""
        updated = queryset.count()
        for conversation in queryset:
            conversation.archive_conversation()
        self.message_user(request, f'{updated} conversations were archived.')
    archive_conversations.short_description = "Archive selected conversations"
    
    def close_conversations(self, request, queryset):
        """Action to close selected conversations."""
        updated = queryset.count()
        for conversation in queryset:
            conversation.close_conversation()
        self.message_user(request, f'{updated} conversations were closed.')
    close_conversations.short_description = "Close selected conversations"
    
    def activate_conversations(self, request, queryset):
        """Action to activate selected conversations."""
        updated = queryset.update(is_active=True, status='active')
        self.message_user(request, f'{updated} conversations were activated.')
    activate_conversations.short_description = "Activate selected conversations"


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    """Admin interface for Message model."""
    
    list_display = (
        'sender', 'conversation_name', 'content_preview', 'message_type', 
        'is_read', 'is_delivered', 'is_important', 'created_at'
    )
    list_filter = (
        'message_type', 'is_read', 'is_delivered', 'is_edited', 'is_important', 
        'is_urgent', 'created_at', 'conversation__conversation_type'
    )
    search_fields = ('content', 'sender__email', 'sender__username')
    readonly_fields = (
        'id', 'created_at', 'updated_at', 'is_edited', 'edited_at', 
        'is_read', 'read_at', 'is_delivered', 'delivered_at'
    )
    
    fieldsets = (
        (None, {
            'fields': ('id', 'conversation', 'thread', 'sender', 'recipient')
        }),
        ('Content', {
            'fields': ('content', 'original_content', 'message_type')
        }),
        ('Status', {
            'fields': ('is_read', 'read_at', 'is_delivered', 'delivered_at', 
                      'is_deleted', 'deleted_at', 'deleted_by')
        }),
        ('Features', {
            'fields': ('is_important', 'is_urgent', 'priority', 'expires_at')
        }),
        ('Metadata', {
            'fields': ('is_edited', 'edited_at', 'created_at', 'updated_at')
        }),
    )
    
    def conversation_name(self, obj):
        """Display conversation name."""
        return obj.conversation.name or f"Conversation {obj.conversation.id}"
    conversation_name.short_description = 'Conversation'
    
    def content_preview(self, obj):
        """Display content preview."""
        content = obj.content[:50]
        if len(obj.content) > 50:
            content += '...'
        return content
    content_preview.short_description = 'Content'
    
    actions = ['mark_as_read', 'mark_as_important', 'mark_as_unimportant']
    
    def mark_as_read(self, request, queryset):
        """Action to mark messages as read."""
        updated = 0
        for message in queryset:
            if not message.is_read:
                message.mark_as_read()
                updated += 1
        self.message_user(request, f'{updated} messages were marked as read.')
    mark_as_read.short_description = "Mark selected messages as read"
    
    def mark_as_important(self, request, queryset):
        """Action to mark messages as important."""
        updated = queryset.update(is_important=True)
        self.message_user(request, f'{updated} messages were marked as important.')
    mark_as_important.short_description = "Mark selected messages as important"
    
    def mark_as_unimportant(self, request, queryset):
        """Action to mark messages as unimportant."""
        updated = queryset.update(is_important=False)
        self.message_user(request, f'{updated} messages were marked as unimportant.')
    mark_as_unimportant.short_description = "Mark selected messages as unimportant"


@admin.register(MessageThread)
class MessageThreadAdmin(admin.ModelAdmin):
    """Admin interface for MessageThread model."""
    
    list_display = ('subject', 'conversation', 'message_count', 'created_at')
    list_filter = ('created_at', 'conversation__conversation_type')
    search_fields = ('subject', 'conversation__name')
    readonly_fields = ('id', 'created_at', 'updated_at')
    
    inlines = [MessageInline]
    
    def message_count(self, obj):
        """Display message count in thread."""
        return obj.messages.count()
    message_count.short_description = 'Messages'


@admin.register(MessageAttachment)
class MessageAttachmentAdmin(admin.ModelAdmin):
    """Admin interface for MessageAttachment model."""
    
    list_display = ('filename', 'message_preview', 'file_type', 'human_readable_size', 'created_at')
    list_filter = ('file_type', 'created_at')
    search_fields = ('filename', 'message__content')
    readonly_fields = ('id', 'file_size', 'human_readable_size', 'created_at')
    
    fieldsets = (
        (None, {
            'fields': ('id', 'message', 'file', 'filename')
        }),
        ('File Information', {
            'fields': ('file_type', 'file_size', 'human_readable_size', 'mime_type')
        }),
        ('Status', {
            'fields': ('is_deleted', 'deleted_at')
        }),
        ('Metadata', {
            'fields': ('created_at',)
        }),
    )
    
    def message_preview(self, obj):
        """Display message content preview."""
        content = obj.message.content[:30]
        if len(obj.message.content) > 30:
            content += '...'
        return content
    message_preview.short_description = 'Message'