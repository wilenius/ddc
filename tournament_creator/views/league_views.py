"""
Sign-up leagues: directors set the time slots matches can be played at, each
player (doubles: each partner separately) picks the slots they can make, and
the matches are scheduled into them (``league_scheduler``) when the sign-up
closes, or again later from the tournament page.
"""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from ..forms import LeagueDayForm, LeagueSettingsForm
from ..models.base_models import LeagueAvailability, LeagueSlot, Matchup, Player, TournamentChart
from .signup_views import _own_player


def slots_by_day(slots):
    """[(date, [slot, ...]), ...] in date order."""
    days = {}
    for slot in slots:
        days.setdefault(slot.date, []).append(slot)
    return sorted(days.items())


def league_signup_status(tournament):
    """Per signed-up player: (signup, player, times saved?), in sign-up order."""
    return [(signup, player, signup.times_saved_at(player) is not None)
            for signup in tournament.signups.select_related('player', 'partner')
            for player in signup.players()]


def _signup_of(tournament, player):
    return next((s for s in tournament.signups.select_related('player', 'partner')
                 if player in s.players()), None)


def _matchup_players(matchup):
    players = [matchup.get_team1_player1(), matchup.get_team1_player2(),
               matchup.get_team2_player1(), matchup.get_team2_player2()]
    return frozenset(p.id for p in players if p)


def _seeded_order(matchup):
    """Position in the seeded schedule: stage, round, then the weaker matches of a
    round before the stronger ones (higher combined seed / ranking first)."""
    if matchup.pair1_id:
        strength = (matchup.pair1.seed or 0) + (matchup.pair2.seed or 0)
    else:
        strength = sum(p.ranking or 0 for p in (matchup.pair1_player1, matchup.pair1_player2,
                                                matchup.pair2_player1, matchup.pair2_player2) if p)
    return (matchup.stage.stage_number if matchup.stage_id else 0, matchup.round_number, -strength)


@transaction.atomic
def schedule_from_availability(tournament, keep_scheduled=False):
    """
    Schedule the league's unplayed matches into the slots from today on. Played
    matches keep their slot; with ``keep_scheduled`` so do matches that already have
    a date, and only the unplaced ones are scheduled. Returns (result, message).
    """
    from ..league_scheduler import FixedMatch, Match, Slot, schedule_league

    today = timezone.localdate()
    db_slots = list(tournament.league_slots.all())
    slot_at = {(s.date, s.start_time): s.id for s in db_slots}
    open_slots = [Slot(s.id, s.date, s.start_time) for s in db_slots if s.date >= today]
    availability = {}
    for player_id, slot_id in LeagueAvailability.objects.filter(
            slot__tournament=tournament).values_list('player_id', 'slot_id'):
        availability.setdefault(player_id, set()).add(slot_id)

    matchups = list(tournament.matchups.select_related(
        'stage', 'pair1__player1', 'pair1__player2', 'pair2__player1', 'pair2__player2',
        'pair1_player1', 'pair1_player2', 'pair2_player1', 'pair2_player2',
    ).prefetch_related('scores'))
    to_schedule, fixed = [], []
    for matchup in matchups:
        played = bool(matchup.scores.all())
        keep = played or (keep_scheduled and matchup.match_date is not None)
        if keep:
            slot_id = slot_at.get((matchup.match_date, matchup.match_time))
            if slot_id is not None:
                fixed.append(FixedMatch(_matchup_players(matchup), slot_id, matchup.court_number))
        else:
            to_schedule.append(matchup)

    result = schedule_league(
        [Match(m.id, _matchup_players(m), _seeded_order(m)) for m in to_schedule],
        open_slots, availability,
        courts=tournament.league_courts,
        max_per_day=tournament.league_max_matches_per_day,
        allow_back_to_back=tournament.league_back_to_back,
        avoid_parallel=tournament.league_avoid_parallel,
        fixed=fixed,
    )
    slot_by_id = {s.id: s for s in db_slots}
    for matchup in to_schedule:
        if matchup.id in result.assignments:
            slot_id, court = result.assignments[matchup.id]
            matchup.match_date = slot_by_id[slot_id].date
            matchup.match_time = slot_by_id[slot_id].start_time
            matchup.court_number = court
        else:
            matchup.match_date = matchup.match_time = None
    Matchup.objects.bulk_update(to_schedule, ['match_date', 'match_time', 'court_number'])

    placed = len(result.assignments)
    message = f"Scheduled {placed} match{'es' if placed != 1 else ''}."
    if result.unscheduled:
        count = len(result.unscheduled)
        message += (f" {count} match{'es' if count != 1 else ''} didn't fit any time slot its players "
                    f"can all make; add slots or assign {'them' if count != 1 else 'it'} by hand.")
    if not result.optimal:
        message += " (Scheduling stopped at its time limit, so the schedule may not be the best possible.)"
    return result, message


@login_required
def league_times(request, tournament_id):
    """A player picks the league slots they can play in. Directors can pick for any
    signed-up player (``?player=<id>``), e.g. for partners without an account."""
    tournament = get_object_or_404(TournamentChart, id=tournament_id)
    if not tournament.is_signup_league:
        return redirect('tournament_detail', pk=tournament_id)
    can_administer = tournament.user_can_administer(request.user)
    own_player = _own_player(request.user)

    player_id = request.GET.get('player') or request.POST.get('player')
    if player_id and can_administer:
        player = get_object_or_404(Player, id=player_id)
    else:
        player = own_player
    signup = _signup_of(tournament, player) if player else None
    if signup is None:
        messages.error(request, "Sign up first, then pick your times." if player == own_player
                       else "That player isn't signed up.")
        return redirect('tournament_signup', tournament_id=tournament_id)

    slots = list(tournament.league_slots.all())
    if request.method == 'POST':
        chosen = {int(pk) for pk in request.POST.getlist('slots') if pk.isdigit()}
        chosen &= {s.id for s in slots}
        with transaction.atomic():
            LeagueAvailability.objects.filter(player=player, slot__tournament=tournament).exclude(
                slot_id__in=chosen).delete()
            have = set(LeagueAvailability.objects.filter(player=player, slot__tournament=tournament)
                       .values_list('slot_id', flat=True))
            LeagueAvailability.objects.bulk_create(
                LeagueAvailability(signup=signup, player=player, slot_id=slot_id)
                for slot_id in chosen - have)
            signup.mark_times_saved(player)
        who = "Your" if player == own_player else f"{player}'s"
        messages.success(request, f"{who} times are saved ({len(chosen)} of {len(slots)} slots).")
        if player == own_player or not can_administer:
            return redirect('tournament_signup', tournament_id=tournament_id)
        return redirect('league_slots', tournament_id=tournament_id)

    mine = set(LeagueAvailability.objects.filter(player=player, slot__tournament=tournament)
               .values_list('slot_id', flat=True))
    partner = signup.partner_of(player)
    partner_times = set()
    partner_answered = False
    if partner:
        partner_times = set(LeagueAvailability.objects.filter(player=partner, slot__tournament=tournament)
                            .values_list('slot_id', flat=True))
        partner_answered = signup.times_saved_at(partner) is not None
    for slot in slots:
        slot.mine = slot.id in mine
        slot.partner = slot.id in partner_times

    return render(request, 'tournament_creator/league_times.html', {
        'tournament': tournament,
        'player': player,
        'is_own': player == own_player,
        'partner': partner,
        'partner_answered': partner_answered,
        'days': slots_by_day(slots),
        'answered': signup.times_saved_at(player) is not None,
    })


@login_required
def league_slots(request, tournament_id):
    """Directors: the league's time slots, its scheduling rules and who can play when."""
    tournament = get_object_or_404(TournamentChart, id=tournament_id)
    if not tournament.is_signup_league:
        return redirect('tournament_detail', pk=tournament_id)
    if not tournament.user_can_administer(request.user):
        messages.error(request, "Only this tournament's directors can edit the time slots.")
        return redirect('tournament_signup', tournament_id=tournament_id)

    day_form = LeagueDayForm(prefix='day')
    settings_form = LeagueSettingsForm(instance=tournament, prefix='rules')
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'add_day':
            day_form = LeagueDayForm(request.POST, prefix='day')
            if day_form.is_valid():
                day = day_form.cleaned_data['date']
                existing = set(tournament.league_slots.filter(date=day).values_list('start_time', flat=True))
                new = [t for t in day_form.cleaned_data['times'] if t not in existing]
                LeagueSlot.objects.bulk_create(
                    LeagueSlot(tournament=tournament, date=day, start_time=t) for t in new)
                messages.success(request, f"Added {len(new)} time slot{'s' if len(new) != 1 else ''} on {day:%d.%m.%Y}.")
                return redirect('league_slots', tournament_id=tournament_id)
        elif action == 'delete_slot':
            slot = get_object_or_404(LeagueSlot, id=request.POST.get('slot'), tournament=tournament)
            slot.delete()
            messages.success(request, f"Removed the slot {slot}.")
            return redirect('league_slots', tournament_id=tournament_id)
        elif action == 'rules':
            settings_form = LeagueSettingsForm(request.POST, instance=tournament, prefix='rules')
            if settings_form.is_valid():
                settings_form.save()
                messages.success(request, "Scheduling rules saved.")
                return redirect('league_slots', tournament_id=tournament_id)

    slots = list(tournament.league_slots.all())
    status = league_signup_status(tournament)
    available = {}
    for slot_id, player_id in LeagueAvailability.objects.filter(
            slot__tournament=tournament).values_list('slot_id', 'player_id'):
        available.setdefault(slot_id, set()).add(player_id)
    players = [player for _signup, player, _saved in status]
    names = {p.id: str(p) for p in players}
    for slot in slots:
        ids = available.get(slot.id, set())
        slot.available_count = len(ids)
        slot.available_names = ', '.join(sorted(names[i] for i in ids if i in names))

    return render(request, 'tournament_creator/league_slots.html', {
        'tournament': tournament,
        'days': slots_by_day(slots),
        'day_form': day_form,
        'settings_form': settings_form,
        'status': status,
        'player_count': len(players),
        'missing_count': sum(1 for _s, _p, saved in status if not saved),
    })


@login_required
@require_POST
def league_schedule(request, tournament_id):
    """Directors: schedule the unplaced matches, or reschedule all unplayed ones."""
    tournament = get_object_or_404(TournamentChart, id=tournament_id)
    if not tournament.user_can_administer(request.user):
        messages.error(request, "Only this tournament's directors can schedule matches.")
        return redirect('tournament_detail', pk=tournament_id)
    if not tournament.is_signup_league or tournament.awaiting_signups:
        return redirect('tournament_detail', pk=tournament_id)
    _result, message = schedule_from_availability(
        tournament, keep_scheduled=request.POST.get('mode') != 'all')
    messages.success(request, message)
    return redirect('tournament_detail', pk=tournament_id)


@login_required
@require_POST
def simulate_league_signups(request, tournament_id):
    """Practice sign-up leagues: fill the sign-up with random ranking players and
    everyone's missing times with random availability."""
    tournament = get_object_or_404(TournamentChart, id=tournament_id)
    if not (tournament.is_sandbox and tournament.is_signup_league and tournament.awaiting_signups):
        messages.error(request, "Only practice leagues awaiting sign-ups can be simulated.")
        return redirect('tournament_signup', tournament_id=tournament_id)
    from ..simulation import simulate_availability, simulate_signups
    added = simulate_signups(tournament, request.user)
    answered = simulate_availability(tournament)
    messages.success(request, f"Added {added} simulated entr{'ies' if added != 1 else 'y'} and "
                              f"picked times for {answered} player{'s' if answered != 1 else ''}.")
    return redirect('tournament_signup', tournament_id=tournament_id)
