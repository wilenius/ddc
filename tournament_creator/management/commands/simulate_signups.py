"""
Fill a sign-up tournament with random entries and, for sign-up leagues, random
time slot availability (the simulation lives in tournament_creator/simulation.py,
shared with the practice league's "Simulate sign-ups & times" button).

Examples:
    python manage.py simulate_signups 42               # fill to the maximum, pick missing times
    python manage.py simulate_signups 42 --times-only  # only pick missing times
    python manage.py simulate_signups 42 --seed 1      # reproducible
"""
import random

from django.core.management.base import BaseCommand, CommandError

from tournament_creator.models.base_models import TournamentChart
from tournament_creator.simulation import simulate_availability, simulate_signups


class Command(BaseCommand):
    help = "Fill a sign-up tournament with random entries and league time slot picks."

    def add_arguments(self, parser):
        parser.add_argument('tournament_id', type=int, help='TournamentChart id')
        parser.add_argument('--times-only', action='store_true',
                            help="Don't add entries; only pick times for players who haven't")
        parser.add_argument('--seed', type=int, default=None, help='Random seed')

    def handle(self, *args, **options):
        try:
            tournament = TournamentChart.objects.get(id=options['tournament_id'])
        except TournamentChart.DoesNotExist:
            raise CommandError(f"Tournament {options['tournament_id']} does not exist")
        if not tournament.awaiting_signups:
            raise CommandError(f"{tournament.name} isn't awaiting sign-ups")
        rng = random.Random(options['seed'])

        if not options['times_only']:
            added = simulate_signups(tournament, tournament.created_by, rng=rng)
            self.stdout.write(f"Added {added} entries to {tournament.name}.")
        if tournament.is_signup_league:
            answered = simulate_availability(tournament, rng=rng)
            self.stdout.write(f"Picked times for {answered} players.")
