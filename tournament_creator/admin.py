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
import functools # Added import

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
        # Check if we are editing an existing object and its backend_name is 'email'
        if obj and obj.backend_name == 'email':
            initial_data = obj.config or {}
            # Return a functools.partial that, when called, will produce an
            # instance of EmailBackendConfigForm, pre-filled with initial_data.
            # This form instance will then be used by the admin.
            return functools.partial(EmailBackendConfigForm, initial=initial_data)
        
        # If it's not an 'email' backend being edited, or if it's an add view (obj is None),
        # proceed with the default behavior.
        # Crucially, remove 'initial' from kwargs if it was added, as the default
        # modelform_factory path might not expect it.
        kwargs.pop('initial', None) 
        return super().get_form(request, obj, change=change, **kwargs)

    def get_fieldsets(self, request, obj=None):
        if obj and obj.backend_name == 'email':
            # Define fieldsets for the EmailBackendConfigForm fields
            # These field names must match the keys in EmailBackendConfigForm.base_fields
            email_form_fields = list(EmailBackendConfigForm.base_fields.keys())
            return (
                (None, {'fields': ('backend_name', 'is_active')}),
                ('Email Configuration', {'fields': email_form_fields}),
            )
        # Default fieldsets for add view or non-email backends
        return super().get_fieldsets(request, obj)

    def save_model(self, request, obj, form, change):
        if obj.backend_name == 'email' and isinstance(form, EmailBackendConfigForm):
            # For email backends, save cleaned_data from EmailBackendConfigForm into obj.config
            new_config = form.cleaned_data.copy()
            
            # Preserve password if it's blank in the form and obj already exists (is being changed)
            if change and obj.pk and 'password' in new_config and not new_config.get('password'):
                if obj.config and isinstance(obj.config, dict) and obj.config.get('password'):
                    new_config['password'] = obj.config.get('password')
                elif 'password' in new_config: # If password was optional and not provided, remove from config
                    del new_config['password']

            obj.config = new_config
        
        # For non-email backends or if the form is not EmailBackendConfigForm (e.g. add view),
        # the default save_model will handle saving obj.config if it's part of the form.
        # If it's an add view for an email backend, obj.config will be saved directly
        # if 'config' was in the ModelForm.
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
