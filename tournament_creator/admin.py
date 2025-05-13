from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models.base_models import Player, TournamentChart, TournamentPlayer, Matchup, TournamentArchetype
from .models.tournament_types import MonarchOfTheCourt8, FourPairsSwedishFormat, EightPairsSwedishFormat
from .models.scoring import MatchScore, PlayerScore
from .models.auth import User
from .models.logging import MatchResultLog

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
