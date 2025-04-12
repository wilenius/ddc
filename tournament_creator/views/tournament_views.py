import json
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.shortcuts import get_object_or_404
from django.http import JsonResponse
from django.db import models
from ..models.base_models import Matchup, TournamentChart
from ..models.scoring import MatchScore, PlayerScore
from ..models.logging import MatchResultLog

@login_required
@require_POST
def record_match_result(request, tournament_id, matchup_id):
    matchup = get_object_or_404(Matchup, id=matchup_id)
    tournament = get_object_or_404(TournamentChart, id=tournament_id)

    team1_scores = json.loads(request.POST.get('team1_scores', '[]'))
    team2_scores = json.loads(request.POST.get('team2_scores', '[]'))
    winning_team = int(request.POST.get('winning_team'))

    if len(team1_scores) != len(team2_scores) or not team1_scores:
        return JsonResponse({'status': 'error', 'message': 'Invalid score data'})

    # Identify model: Pairs (Pair FKs) or MoC (individual players)
    if getattr(matchup, 'pair1', None) and getattr(matchup, 'pair2', None):
        players = [matchup.pair1.player1, matchup.pair1.player2, matchup.pair2.player1, matchup.pair2.player2]
    else:
        players = [
            getattr(matchup, 'pair1_player1', None),
            getattr(matchup, 'pair1_player2', None),
            getattr(matchup, 'pair2_player1', None),
            getattr(matchup, 'pair2_player2', None),
        ]
    players = [p for p in players if p]

    matchup.scores.all().delete()
    for set_num, (s1, s2) in enumerate(zip(team1_scores, team2_scores), 1):
        MatchScore.objects.create(
            matchup=matchup,
            set_number=set_num,
            team1_score=s1,
            team2_score=s2,
            winning_team=winning_team,
            point_difference=(s1 - s2 if winning_team == 1 else s2 - s1)
        )

    MatchResultLog.objects.create(
        matchup=matchup,
        recorded_by=request.user,
        action='UPDATE',
        details={
            'team1_scores': team1_scores,
            'team2_scores': team2_scores,
            'winning_team': winning_team,
        }
    )

    for player in players:
        player_score, _ = PlayerScore.objects.get_or_create(
            tournament=tournament,
            player=player
        )
        all_played = Matchup.objects.filter(
            tournament_chart=tournament
        ).filter(
            models.Q(pair1_player1=player) | models.Q(pair1_player2=player) |
            models.Q(pair2_player1=player) | models.Q(pair2_player2=player)
        ).distinct()
        player_score.matches_played = all_played.count()
        player_score.wins = 0
        player_score.total_point_difference = 0
        for m in all_played:
            scores = list(m.scores.order_by('set_number'))
            if not scores:
                continue
            for s in scores:
                on_team1 = (player in [getattr(m, 'pair1_player1', None), getattr(m, 'pair1_player2', None)])
                on_team2 = (player in [getattr(m, 'pair2_player1', None), getattr(m, 'pair2_player2', None)])
                if on_team1 and s.winning_team == 1:
                    player_score.wins += 1
                    player_score.total_point_difference += s.point_difference
                elif on_team2 and s.winning_team == 2:
                    player_score.wins += 1
                    player_score.total_point_difference += s.point_difference
                elif on_team1 and s.winning_team == 2:
                    player_score.total_point_difference -= s.point_difference
                elif on_team2 and s.winning_team == 1:
                    player_score.total_point_difference -= s.point_difference
        player_score.save()

    return JsonResponse({'status': 'success'})
