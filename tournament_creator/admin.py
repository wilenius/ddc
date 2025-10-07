from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models.base_models import Player, TournamentChart, TournamentPlayer, Matchup, TournamentArchetype
from .models.tournament_types import MonarchOfTheCourt8, FourPairsSwedishFormat, EightPairsSwedishFormat
from .models.scoring import MatchScore, PlayerScore
from .models.auth import User
from .models.logging import MatchResultLog
from .models.notifications import NotificationBackendSetting, NotificationLog
from .forms import EmailBackendConfigForm, SignalBackendConfigForm, TournamentCreationForm
from django.utils.text import Truncator
# import functools # Removed import

class CustomUserAdmin(UserAdmin):
    model = User
    list_display = ['username', 'email', 'role', 'is_staff']
    fieldsets = UserAdmin.fieldsets + (
        ('Role', {'fields': ('role',)}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Role', {'fields': ('role',)}),
    )

admin.site.register(User, CustomUserAdmin)

@admin.register(Player)
class PlayerAdmin(admin.ModelAdmin):
    list_display = ('first_name', 'last_name', 'ranking')
    ordering = ('ranking',)

@admin.register(TournamentChart)
class TournamentChartAdmin(admin.ModelAdmin):
    form = TournamentCreationForm
    list_display = ('name', 'date', 'end_date', 'number_of_rounds', 'number_of_courts')
    ordering = ('-date',)
    fieldsets = [
        (None, {'fields': ('name', 'date', 'end_date', 'name_display_format')}),
        ('Notification Settings', {
            'fields': ('notify_by_email', 'notify_by_signal', 'notify_by_matrix')
        }),
        ('Signal Recipients (Optional - overrides global settings)', {
            'fields': ('signal_groups_picker', 'signal_recipient_usernames', 'signal_recipient_group_ids'),
            'classes': ('collapse',)
        })
    ]

@admin.register(Matchup)
class MatchupAdmin(admin.ModelAdmin):
    list_display = ('tournament_chart', 'round_number', 'court_number')
    ordering = ('tournament_chart', 'round_number', 'court_number')

@admin.register(TournamentArchetype)
class TournamentArchetypeAdmin(admin.ModelAdmin):
    list_display = ('name', 'description', 'tournament_category')
    fields = ('name', 'description', 'tournament_category', 'notes')
    list_filter = ('tournament_category',)

@admin.register(MatchScore)
class MatchScoreAdmin(admin.ModelAdmin):
    list_display = ('matchup', 'set_number', 'team1_score', 'team2_score', 'winning_team', 'point_difference')
    ordering = ('matchup', 'set_number')

@admin.register(PlayerScore)
class PlayerScoreAdmin(admin.ModelAdmin):
    list_display = ('tournament', 'player', 'wins', 'matches_played', 'total_point_difference')
    ordering = ('tournament', '-wins', '-total_point_difference')

@admin.register(MatchResultLog)
class MatchResultLogAdmin(admin.ModelAdmin):
    list_display = ('matchup', 'recorded_by', 'recorded_at', 'action')
    ordering = ('-recorded_at',)
    readonly_fields = ('recorded_at', 'details')

# Note: Abstract models can't be registered directly in admin
# The concrete TournamentArchetype objects from the database
# are already registered via TournamentArchetypeAdmin above

@admin.register(NotificationBackendSetting)
class NotificationBackendSettingAdmin(admin.ModelAdmin):
    list_display = ('backend_name', 'is_active', 'config')
    list_editable = ('is_active',)
    search_fields = ('backend_name',)

    class Media:
        js = ('admin/js/signal_groups_refresh.js',)
        css = {
            'all': ('admin/css/signal_admin.css',)
        }

    def get_form(self, request, obj=None, change=False, **kwargs):
        if obj and obj.backend_name == 'email':
            kwargs['form'] = EmailBackendConfigForm
        elif obj and obj.backend_name == 'signal':
            kwargs['form'] = SignalBackendConfigForm
        # functools.partial is no longer needed here as the form's __init__ handles initial data.
        return super().get_form(request, obj, change=change, **kwargs)

    def get_fieldsets(self, request, obj=None):
        if obj and obj.backend_name == 'email':
            # These are the custom fields explicitly defined on EmailBackendConfigForm
            email_specific_fields = ['recipient_list', 'from_email', 'host', 'port', 'username', 'password', 'use_tls', 'use_ssl']
            return [
                # backend_name and is_active are from EmailBackendConfigForm.Meta.fields
                (None, {'fields': ('backend_name', 'is_active')}), 
                ('Email Configuration', {'fields': email_specific_fields})
            ]
        elif obj and obj.backend_name == 'signal':
            signal_specific_fields = ['signal_cli_rest_api_url', 'signal_sender_phone_number', 'recipient_usernames', 'recipient_groups_picker', 'recipient_group_ids']
            return [
                (None, {'fields': ('backend_name', 'is_active')}),
                ('Signal Configuration', {'fields': signal_specific_fields})
            ]
        # Default for add view or non-email backends (uses default ModelAdmin fieldsets)
        return super().get_fieldsets(request, obj) 

    def save_model(self, request, obj, form, change):
        # The ModelForm (EmailBackendConfigForm, SignalBackendConfigForm or default) will have cleaned data for its fields.
        # backend_name and is_active are handled by the ModelForm part.
        # We need to populate obj.config for the custom fields based on the backend type.

        if obj.backend_name == 'email' and isinstance(form, EmailBackendConfigForm):
            new_config = {}
            current_password = None

            # If editing an existing object with a password in its config
            if obj.pk and obj.config and obj.config.get('password'):
                current_password = obj.config.get('password')

            custom_field_keys = ['recipient_list', 'from_email', 'host', 'port', 'username', 'password', 'use_tls', 'use_ssl']
            for field_name in custom_field_keys:
                # Get the value from the form's cleaned_data
                new_config[field_name] = form.cleaned_data.get(field_name)
            
            # Password handling:
            if not new_config.get('password'): # If the password field in the form is empty/None
                if current_password: # And an old password exists
                    new_config['password'] = current_password # Preserve it
                else: # No new password and no old password, so remove key if it exists
                    if 'password' in new_config:
                        del new_config['password']
            # If a new password IS provided in the form, it will be used from form.cleaned_data.get('password')
            obj.config = new_config
        
        elif obj.backend_name == 'signal' and isinstance(form, SignalBackendConfigForm):
            new_config = {}
            custom_field_keys = ['signal_cli_rest_api_url', 'signal_sender_phone_number', 'recipient_usernames']
            for field_name in custom_field_keys:
                new_config[field_name] = form.cleaned_data.get(field_name)

            # Combine group picker selections with manual group IDs
            selected_groups = form.cleaned_data.get('recipient_groups_picker', [])
            manual_group_ids = form.cleaned_data.get('recipient_group_ids', '')

            # Combine both sources
            all_group_ids = list(selected_groups)  # Start with picker selections
            if manual_group_ids and manual_group_ids.strip():
                manual_ids = [gid.strip() for gid in manual_group_ids.split(',') if gid.strip()]
                # Add manual IDs that aren't already in the list
                for gid in manual_ids:
                    if gid not in all_group_ids:
                        all_group_ids.append(gid)

            # Store as comma-separated string
            new_config['recipient_group_ids'] = ', '.join(all_group_ids) if all_group_ids else ''
            obj.config = new_config
        
        # Call super().save_model() to save the NotificationBackendSetting instance.
        # This handles saving fields defined in ModelForm.Meta.fields (backend_name, is_active)
        # and any other standard ModelForm save procedures.
        super().save_model(request, obj, form, change)

@admin.register(NotificationLog)
class NotificationLogAdmin(admin.ModelAdmin):
    list_display = ('timestamp', 'backend_setting', 'success', 'match_result_log', 'short_details_display')
    list_filter = ('backend_setting__backend_name', 'success')
    search_fields = ('details', 'match_result_log__matchup__tournament_chart__name', 'backend_setting__backend_name')
    readonly_fields = ('timestamp', 'backend_setting', 'success', 'details', 'match_result_log')

    def short_details_display(self, obj):
        return Truncator(obj.details).chars(50)
    short_details_display.short_description = 'Details Snippet'
