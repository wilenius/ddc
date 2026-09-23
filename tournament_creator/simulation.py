"""
Simulated, ranking-weighted match results for testing: used by the
``simulate_scores`` management command and the practice tournament's
"Simulate results" button.

Match outcomes are driven by ranking probabilities: the closer two teams'
ranking points, the closer the simulated match, with a real chance of upsets.
"""
import json
import math
import random

from django.test import RequestFactory

# Per-point win probability for the strongest possible mismatch in the
# tournament. 0.60 over a race to 15 gives the favourite roughly a 90% match
# win probability, so upsets still happen; evenly ranked teams sit near 0.50
# and produce close scores.
MAX_POINT_EDGE = 0.10
# Per-set "form of the day" jitter, so identical pairings don't always
# produce identical-looking scorelines.
FORM_JITTER = 0.03


def team_strengths(matchup):
    """Ranking points of each side; works for pairs and MoC matchups."""
    if matchup.pair1_id and matchup.pair2_id:
        return matchup.pair1.ranking_points_sum, matchup.pair2.ranking_points_sum
    team1 = [matchup.pair1_player1, matchup.pair1_player2]
    team2 = [matchup.pair2_player1, matchup.pair2_player2]
    return (sum(p.ranking_points for p in team1 if p),
            sum(p.ranking_points for p in team2 if p))


def strength_spread(matchups):
    """Largest strength gap across the matchups, used to normalize edges."""
    diffs = [abs(a - b) for a, b in (team_strengths(m) for m in matchups)]
    return max(diffs, default=0) or 1.0


def simulate_set(strength1, strength2, spread, points, cap):
    """Play a set point by point: to ``points``, win by 2, hard cap at ``cap``."""
    edge = MAX_POINT_EDGE * math.tanh(2.0 * (strength1 - strength2) / spread)
    p_team1 = 0.5 + edge + random.uniform(-FORM_JITTER, FORM_JITTER)
    points1 = points2 = 0
    while True:
        if random.random() < p_team1:
            points1 += 1
        else:
            points2 += 1
        leader, trailer = max(points1, points2), min(points1, points2)
        if (leader >= points and leader - trailer >= 2) or leader >= cap:
            return points1, points2


def simulate_match(matchup, spread, points, cap, sets):
    """Best-of-``sets`` match: stops as soon as one team has a majority of the sets.
    Returns (team1_scores, team2_scores)."""
    strength1, strength2 = team_strengths(matchup)
    sets_to_win = sets // 2 + 1
    team1_scores, team2_scores = [], []
    while len(team1_scores) < sets:
        p1, p2 = simulate_set(strength1, strength2, spread, points, cap)
        team1_scores.append(p1)
        team2_scores.append(p2)
        sets_won = sum(1 for a, b in zip(team1_scores, team2_scores) if a > b)
        if max(sets_won, len(team1_scores) - sets_won) >= sets_to_win:
            break
    return team1_scores, team2_scores


def record_result(tournament, matchup, team1_scores, team2_scores, user):
    """
    Record a result through the real scoring view, so PairScore/PlayerScore
    aggregation and the playoff placement-match hook behave exactly as in
    production. Raises ValueError if the view rejects it.
    """
    from .views.tournament_views import record_match_result
    request = RequestFactory().post(
        f'/tournament/{tournament.id}/matchup/{matchup.id}/record/',
        {'team1_scores': json.dumps(team1_scores),
         'team2_scores': json.dumps(team2_scores),
         # Skip the warn-and-confirm format check; a simulation run with other
         # points/cap than the format's needn't match its game structure.
         'confirmed': '1'},
    )
    request.user = user
    response = record_match_result(request, tournament.id, matchup.id)
    result = json.loads(response.content)
    if result.get('status') != 'success':
        raise ValueError(f"Failed to record matchup {matchup.id}: {result.get('message')}")
