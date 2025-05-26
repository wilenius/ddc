from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models.base_models import Player, TournamentChart, TournamentPlayer, Matchup, TournamentArchetype
from .models.tournament_types import MonarchOfTheCourt8, FourPairsSwedishFormat, EightPairsSwedishFormat
from .models.scoring import MatchScore, PlayerScore
from .models.auth import User
from .models.logging import MatchResultLog
from .models.notifications import NotificationBackendSetting, NotificationLog
from django.utils.text import Truncator

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
    list_editable = ('is_active',) # backend_name is unique, not ideal for list_editable
    search_fields = ('backend_name',) # Searching JSON 'config' can be complex

@admin.register(NotificationLog)
class NotificationLogAdmin(admin.ModelAdmin):
    list_display = ('timestamp', 'backend_setting', 'success', 'match_result_log', 'short_details_display')
    list_filter = ('backend_setting__backend_name', 'success')
    search_fields = ('details', 'match_result_log__matchup__tournament_chart__name', 'backend_setting__backend_name')
    readonly_fields = ('timestamp', 'backend_setting', 'success', 'details', 'match_result_log')

    def short_details_display(self, obj):
        return Truncator(obj.details).chars(50)
    short_details_display.short_description = 'Details Snippet'
