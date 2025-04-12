from django.test import TestCase
from django.db import models
from ..models import Player, TournamentChart, TournamentArchetype, Matchup
from ..models.tournament_types import MonarchOfTheCourt8

class TournamentLogicTests(TestCase):
    def setUp(self):
        # Create 8 players
        self.players = []
        for i in range(8):
            player = Player.objects.create(
                first_name=f'Player{i+1}',
                last_name=f'Test',
                ranking=i+1
            )
            self.players.append(player)

        # Create tournament archetype
        self.archetype = MonarchOfTheCourt8.objects.create(
            name="Cade Loving's 8-player KoC",
            description='Test tournament type'
        )

    def test_tournament_generation(self):
        """Test that tournament generates correct number of matches and rounds"""
        tournament = TournamentChart.objects.create(
            name='Test Tournament',
            date='2025-01-01',
            number_of_rounds=7,
            number_of_courts=2
        )
        tournament.players.set(self.players)
        
        self.archetype.generate_matchups(tournament, self.players)
        
        # Check total number of matchups (7 rounds × 2 courts)
        self.assertEqual(Matchup.objects.filter(tournament_chart=tournament).count(), 14)
        
        # Check rounds
        rounds = Matchup.objects.filter(tournament_chart=tournament).values_list(
            'round_number', flat=True).distinct().order_by('round_number')
        self.assertEqual(list(rounds), [1,2,3,4,5,6,7])

        # Check courts per round
        for round_num in range(1, 8):
            court_count = Matchup.objects.filter(
                tournament_chart=tournament,
                round_number=round_num
            ).count()
            self.assertEqual(court_count, 2)

    def test_player_matchups(self):
        """Test that each player gets correct number of matches"""
        tournament = TournamentChart.objects.create(
            name='Test Tournament',
            date='2025-01-01',
            number_of_rounds=7,
            number_of_courts=2
        )
        tournament.players.set(self.players)
        
        self.archetype.generate_matchups(tournament, self.players)
        
        # Each player should play in 7 matches
        for player in self.players:
            match_count = Matchup.objects.filter(
                tournament_chart=tournament
            ).filter(
                models.Q(pair1_player1=player) |
                models.Q(pair1_player2=player) |
                models.Q(pair2_player1=player) |
                models.Q(pair2_player2=player)
            ).count()
            self.assertEqual(
                match_count, 
                7, 
                f"Player {player.first_name} has {match_count} matches instead of 7"
            )

    def test_first_round_seeding(self):
        """Test that first round matches follow the correct seeding pattern"""
        tournament = TournamentChart.objects.create(
            name='Test Tournament',
            date='2025-01-01',
            number_of_rounds=7,
            number_of_courts=2
        )
        tournament.players.set(self.players)
        
        self.archetype.generate_matchups(tournament, self.players)
        
        # Get first round matchups
        round1_matches = Matchup.objects.filter(
            tournament_chart=tournament,
            round_number=1
        ).order_by('court_number')
        
        # Court 1: 1&3 vs 6&8
        court1 = round1_matches[0]
        self.assertEqual(court1.pair1_player1.ranking, 1)
        self.assertEqual(court1.pair1_player2.ranking, 3)
        self.assertEqual(court1.pair2_player1.ranking, 6)
        self.assertEqual(court1.pair2_player2.ranking, 8)
        
        # Court 2: 2&4 vs 5&7
        court2 = round1_matches[1]
        self.assertEqual(court2.pair1_player1.ranking, 2)
        self.assertEqual(court2.pair1_player2.ranking, 4)
        self.assertEqual(court2.pair2_player1.ranking, 5)
        self.assertEqual(court2.pair2_player2.ranking, 7)