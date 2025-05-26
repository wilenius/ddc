from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models.base_models import Player, TournamentChart, TournamentPlayer, Matchup, TournamentArchetype
from .models.tournament_types import MonarchOfTheCourt8, FourPairsSwedishFormat, EightPairsSwedishFormat
from .models.scoring import MatchScore, PlayerScore
from .models.auth import User
from .models.logging import MatchResultLog
from .models.notifications import NotificationBackendSetting, NotificationLog
from .forms import EmailBackendConfigForm
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
    list_display = ('name', 'date', 'number_of_rounds', 'number_of_courts')
    ordering = ('-date',)

@admin.register(Matchup)
class MatchupAdmin(admin.ModelAdmin):
    list_display = ('tournament_chart', 'round_number', 'court_number')
    ordering = ('tournament_chart', 'round_number', 'court_number')

@admin.register(TournamentArchetype)
class TournamentArchetypeAdmin(admin.ModelAdmin):
    list_display = ('name', 'description')

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

    def get_form(self, request, obj=None, change=False, **kwargs):
        if obj and obj.backend_name == 'email':
            kwargs['form'] = EmailBackendConfigForm  # EmailBackendConfigForm is now a ModelForm
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
        # Default for add view or non-email backends (uses default ModelAdmin fieldsets)
        return super().get_fieldsets(request, obj) 

    def save_model(self, request, obj, form, change):
        # The ModelForm (EmailBackendConfigForm or default) will have cleaned data for its fields.
        # backend_name and is_active are handled by the ModelForm part.
        # We need to populate obj.config for the custom fields if it's an email backend.

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
            # If the password field in the form is empty/None:
            if not new_config.get('password'):
                if current_password: # And an old password exists
                    new_config['password'] = current_password # Preserve it
                else: # No new password and no old password, so remove key
                    if 'password' in new_config:
                        del new_config['password']
            # If a new password IS provided in the form, it will be used from form.cleaned_data.get('password')

            obj.config = new_config
        
        # Call super().save_model() to save the NotificationBackendSetting instance.
        # This handles saving fields defined in EmailBackendConfigForm.Meta.fields (backend_name, is_active)
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
