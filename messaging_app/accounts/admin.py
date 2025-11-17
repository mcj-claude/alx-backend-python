from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.html import format_html
from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """Custom admin interface for User model."""
    
    list_display = (
        'email', 'username', 'display_name', 'is_verified', 
        'is_active', 'is_online', 'last_seen', 'created_at'
    )
    list_filter = (
        'is_active', 'is_verified', 'is_suspended', 'is_staff', 
        'is_superuser', 'created_at', 'last_seen', 'preferred_language'
    )
    search_fields = ('email', 'username', 'first_name', 'last_name')
    readonly_fields = (
        'id', 'date_joined', 'last_login', 'password_changed_at', 
        'created_at', 'updated_at'
    )
    
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Personal info', {
            'fields': ('username', 'first_name', 'last_name', 'profile_picture', 
                      'bio', 'date_of_birth', 'phone_number')
        }),
        ('Privacy Settings', {
            'fields': ('is_profile_public', 'is_phone_visible', 'show_online_status')
        }),
        ('Permissions', {
            'fields': ('is_active', 'is_verified', 'is_suspended', 'is_staff', 
                      'is_superuser', 'groups', 'user_permissions')
        }),
        ('Security', {
            'fields': ('two_factor_enabled', 'two_factor_secret', 'login_attempts', 
                      'locked_until', 'last_login_ip')
        }),
        ('Activity', {
            'fields': ('last_seen', 'last_login', 'date_joined', 
                      'password_changed_at', 'created_at', 'updated_at')
        }),
        ('Preferences', {
            'fields': ('preferred_language', 'timezone', 'email_notifications', 
                      'push_notifications')
        }),
    )
    
    def display_name(self, obj):
        """Return user's display name."""
        return obj.display_name
    display_name.short_description = 'Display Name'
    
    def is_online(self, obj):
        """Show online status."""
        if obj.is_online():
            return format_html('<span style="color: green;">●</span> Online')
        else:
            return format_html('<span style="color: gray;">○</span> Offline')
    is_online.boolean = True
    is_online.short_description = 'Online Status'
    
    def get_queryset(self, request):
        """Optimize queryset with select_related."""
        qs = super().get_queryset(request)
        return qs.select_related()
    
    actions = ['verify_users', 'suspend_users', 'activate_users']
    
    def verify_users(self, request, queryset):
        """Action to verify selected users."""
        updated = queryset.update(is_verified=True)
        self.message_user(request, f'{updated} users were successfully verified.')
    verify_users.short_description = "Verify selected users"
    
    def suspend_users(self, request, queryset):
        """Action to suspend selected users."""
        updated = queryset.update(is_suspended=True)
        self.message_user(request, f'{updated} users were successfully suspended.')
    suspend_users.short_description = "Suspend selected users"
    
    def activate_users(self, request, queryset):
        """Action to activate selected users."""
        updated = queryset.update(is_active=True, is_suspended=False)
        self.message_user(request, f'{updated} users were successfully activated.')
    activate_users.short_description = "Activate selected users"