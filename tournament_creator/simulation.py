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


def simulate_signups(tournament, user, rng=random):
    """
    Fill a sign-up with random ranking players (doubles: random pairs) up to its
    maximum, as if they had signed up themselves. Returns the number of entries added.
    """
    from .models.base_models import Player, TournamentSignup
    signups = list(tournament.signups.all())
    entered = {p.id for s in signups for p in s.players()}
    free = list(Player.objects.exclude(id__in=entered))
    rng.shuffle(free)
    per_entry = 2 if tournament.signup_category == 'PAIRS' else 1
    wanted = max(0, (tournament.signup_max or len(signups)) - len(signups))
    added = 0
    while added < wanted and len(free) >= per_entry:
        player = free.pop()
        partner = free.pop() if per_entry == 2 else None
        TournamentSignup.objects.create(tournament=tournament, player=player, partner=partner,
                                        signed_up_by=user)
        added += 1
    return added


def simulate_availability(tournament, rng=random):
    """
    Pick league time slots for every signed-up player who hasn't answered yet:
    each player can make a random share of the slots, skips some days entirely,
    and doubles partners mostly pick alike. Returns the number of players answered.
    """
    from .models.base_models import LeagueAvailability
    slots = list(tournament.league_slots.all())
    days = {s.date for s in slots}
    answered = 0
    for signup in tournament.signups.select_related('player', 'partner'):
        first_picks = None
        for player in signup.players():
            if signup.times_saved_at(player) is not None:
                continue
            rate = rng.uniform(0.4, 0.85)
            free_days = {d for d in days if rng.random() > 0.25}
            picks = {s.id for s in slots if s.date in free_days and rng.random() < rate}
            if first_picks is not None:
                # A partner's week often looks like their partner's
                picks = {sid for sid in first_picks if rng.random() < 0.8} | {
                    sid for sid in picks if rng.random() < 0.3}
            first_picks = picks
            LeagueAvailability.objects.filter(player=player, slot__tournament=tournament).delete()
            LeagueAvailability.objects.bulk_create(
                LeagueAvailability(signup=signup, player=player, slot_id=sid) for sid in picks)
            signup.mark_times_saved(player)
            answered += 1
    return answered
