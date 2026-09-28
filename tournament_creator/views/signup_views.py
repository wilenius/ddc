"""
Sign-up tournaments: players enter themselves (doubles: with their partner) until
the deadline, then a director closes the sign-up, which picks the format from the
number of entries and creates the schedule (``create_tournament_schedule``).
"""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ObjectDoesNotExist
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from ..forms import TournamentSignupForm
from ..models.base_models import TournamentChart, TournamentSignup
from ..models.tournament_types import PAIRS_FORMAT_OPTIONS
from .tournament_views import create_tournament_schedule


def _own_player(user):
    """The viewer's ranking player, if their account may sign up (player status)."""
    if not (user.is_player() or user.can_create_tournaments()):
        return None
    try:
        return user.player
    except (AttributeError, ObjectDoesNotExist):
        return None


def _can_withdraw(tournament, signup, user, can_administer):
    """Directors can remove any entry; players their own while sign-up is open."""
    if can_administer:
        return True
    if not tournament.signup_is_open():
        return False
    player = _own_player(user)
    return signup.signed_up_by_id == user.pk or (player is not None and player in signup.players())


@login_required
def tournament_signup(request, tournament_id):
    tournament = get_object_or_404(TournamentChart, id=tournament_id)
    if not tournament.awaiting_signups:
        return redirect('tournament_detail', pk=tournament_id)

    user = request.user
    can_administer = tournament.user_can_administer(user)
    own_player = _own_player(user)
    self_form = TournamentSignupForm(tournament, own_player=own_player, prefix='me') if own_player else None
    add_form = TournamentSignupForm(tournament, prefix='add') if can_administer else None

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'withdraw':
            signup = get_object_or_404(TournamentSignup, id=request.POST.get('signup'), tournament=tournament)
            if _can_withdraw(tournament, signup, user, can_administer):
                names = ' & '.join(str(p) for p in signup.players())
                signup.delete()
                messages.success(request, f"{names} withdrawn from the tournament.")
            else:
                messages.error(request, "You can't withdraw this entry.")
            return redirect('tournament_signup', tournament_id=tournament_id)

        if action == 'signup' and own_player:
            self_form = TournamentSignupForm(tournament, request.POST, own_player=own_player, prefix='me')
            if not tournament.signup_is_open():
                messages.error(request, "The sign-up deadline has passed.")
                return redirect('tournament_signup', tournament_id=tournament_id)
            form = self_form
        elif action == 'add' and can_administer:
            add_form = TournamentSignupForm(tournament, request.POST, prefix='add')
            form = add_form
        else:
            messages.error(request, "You can't sign up for this tournament.")
            return redirect('tournament_signup', tournament_id=tournament_id)

        if form.is_valid():
            signup = TournamentSignup.objects.create(
                tournament=tournament,
                player=form.cleaned_data['player'],
                partner=form.cleaned_data.get('partner'),
                signed_up_by=user,
            )
            names = ' & '.join(str(p) for p in signup.players())
            messages.success(request, f"{names} signed up." if action == 'add' else "You're signed up!")
            return redirect('tournament_signup', tournament_id=tournament_id)

    signups = list(tournament.signups.select_related('player', 'partner', 'signed_up_by'))
    for signup in signups:
        signup.can_withdraw = _can_withdraw(tournament, signup, user, can_administer)
    # Sign-up leagues: who has picked their time slots
    league = tournament.is_signup_league
    missing_times = []
    if league:
        for signup in signups:
            signup.player_answered = signup.player_times_saved_at is not None
            signup.partner_answered = signup.partner_times_saved_at is not None
            missing_times += [p for p in signup.players() if signup.times_saved_at(p) is None]
    my_signup = next((s for s in signups if own_player and own_player in s.players()), None)
    is_pairs = tournament.signup_category == 'PAIRS'
    pairs_format = next((o for o in PAIRS_FORMAT_OPTIONS if o['key'] == tournament.signup_pairs_format), None)

    return render(request, 'tournament_creator/tournament_signup.html', {
        'tournament': tournament,
        'signups': signups,
        'my_signup': my_signup,
        'self_form': self_form,
        'add_form': add_form,
        'can_administer': can_administer,
        'signup_open': tournament.signup_is_open(),
        'is_full': bool(tournament.signup_max) and len(signups) >= tournament.signup_max,
        'below_minimum': len(signups) < (tournament.signup_min or 0),
        'is_pairs': is_pairs,
        'unit': 'pairs' if is_pairs else 'players',
        'format_label': (pairs_format['label'] if pairs_format else 'Round robin') if is_pairs
                        else 'Monarch of the Court',
        'directors': [d for d in [tournament.created_by, *tournament.directors.all()] if d],
        'is_league': league,
        'slot_count': tournament.league_slots.count() if league else 0,
        'missing_times': missing_times,
        'my_times_answered': bool(league and my_signup and my_signup.times_saved_at(own_player)),
        'my_times_count': (tournament.league_slots.filter(availabilities__player=own_player).count()
                           if league and own_player else 0),
    })


@login_required
@require_POST
def close_signup(request, tournament_id):
    """Close the sign-up and create the schedule from the entries, in sign-up order."""
    tournament = get_object_or_404(TournamentChart, id=tournament_id)
    if not tournament.user_can_administer(request.user):
        messages.error(request, "Only this tournament's directors can close the sign-up.")
        return redirect('tournament_signup', tournament_id=tournament_id)
    if not tournament.awaiting_signups:
        return redirect('tournament_detail', pk=tournament_id)

    signups = list(tournament.signups.select_related('player', 'partner'))
    unit = 'pairs' if tournament.signup_category == 'PAIRS' else 'players'
    if len(signups) < (tournament.signup_min or 0):
        messages.error(request, f"Only {len(signups)} {unit} have signed up; the tournament needs at "
                                f"least {tournament.signup_min}. Add entries or delete the tournament.")
        return redirect('tournament_signup', tournament_id=tournament_id)

    players = [player for signup in signups for player in signup.players()]
    try:
        message = create_tournament_schedule(
            tournament, tournament.signup_category, players, tournament.signup_pairs_format)
    except ValueError as e:
        tournament.refresh_from_db()
        messages.error(request, str(e))
        return redirect('tournament_signup', tournament_id=tournament_id)
    if tournament.is_signup_league:
        from .league_views import schedule_from_availability
        _result, schedule_message = schedule_from_availability(tournament)
        message = f"{message} {schedule_message}"
    messages.success(request, f"Sign-up closed. {message}")
    return redirect('tournament_detail', pk=tournament_id)
