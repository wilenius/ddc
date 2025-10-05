from django.urls import path
from django.views.generic import RedirectView
from .views.tournament_views import (
    TournamentListView, TournamentCreateView, TournamentDetailView,
    TournamentDeleteView, TournamentDownloadResultsView, record_match_result, manual_tiebreak_resolution
)
from .views.player_views import (
    PlayerListView, PlayerCreateView, PlayerUpdateView, PlayerDeleteView
)
from .views.autocomplete import PlayerAutocomplete
from .views.rankings_views import (
    RankingsListView, update_rankings, check_update_status
)
from .views.notifications_views import refresh_signal_groups

urlpatterns = [
    path('', RedirectView.as_view(pattern_name='tournament_list', permanent=False)),
    path('tournaments/', TournamentListView.as_view(), name='tournament_list'),
    path('tournaments/create/', TournamentCreateView.as_view(), name='tournament_create'),
    path('tournaments/<int:pk>/', TournamentDetailView.as_view(), name='tournament_detail'),
    path('tournaments/<int:pk>/delete/', TournamentDeleteView.as_view(), name='tournament_delete'),
    path('tournaments/<int:pk>/download/', TournamentDownloadResultsView.as_view(), name='tournament_download_results'),
    path('tournaments/<int:tournament_id>/matchup/<int:matchup_id>/record/',
         record_match_result, name='record_match_result'),
    path('tournaments/<int:tournament_id>/tiebreak/', manual_tiebreak_resolution, name='manual_tiebreak_resolution'),
    path('players/', PlayerListView.as_view(), name='player_list'),
    path('players/create/', PlayerCreateView.as_view(), name='player_create'),
    path('players/<int:pk>/update/', PlayerUpdateView.as_view(), name='player_update'),
    path('players/<int:pk>/delete/', PlayerDeleteView.as_view(), name='player_delete'),
    path('player-autocomplete/', PlayerAutocomplete.as_view(), name='player-autocomplete'),
    
    # Rankings URLs
    path('rankings/', RankingsListView.as_view(), name='rankings_list'),
    path('rankings/update/', update_rankings, name='update_rankings'),
    path('rankings/status/', check_update_status, name='check_rankings_status'),

    # Notifications URLs
    path('api/refresh-signal-groups/', refresh_signal_groups, name='refresh_signal_groups'),
]
