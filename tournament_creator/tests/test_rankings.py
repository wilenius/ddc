from django.test import TestCase
from django.db import models
from ..models import Player, TournamentChart, Matchup
from ..models.tournament_types import MonarchOfTheCourt8
from django.core.exceptions import ValidationError

class RankingBasedMatchupTests(TestCase):
    def setUp(self):
        # Create players with specific rankings
        self.players = []
        player_data = [
            ("Player1", "Test", 1),
            ("Player2", "Test", 2),
            ("Player3", "Test", 3),
            ("Player4", "Test", 4),
            ("Player5", "Test", 5),
            ("Player6", "Test", 6),
            ("Player7", "Test", 7),
            ("Player8", "Test", 8),
        ]
        for fname, lname, rank in player_data:
            player = Player.objects.create(
                first_name=fname,
                last_name=lname,
                ranking=rank
            )
            self.players.append(player)

        # Create tournament archetype
        self.archetype = MonarchOfTheCourt8.objects.create(
            name="Test KoC",
            description="Test tournament type"
        )

    def test_validate_rankings(self):
        """Test that rankings work with sorted players"""
        # Test valid rankings (1-8)
        tournament = TournamentChart.objects.create(
            name='Test Tournament',
            date='2025-01-01',
            number_of_rounds=7,
            number_of_courts=2
        )
        tournament.players.set(self.players)

        # This should work without raising an exception
        self.archetype.generate_matchups(tournament, self.players)

        # Test that matchups were created successfully
        matchups = Matchup.objects.filter(tournament_chart=tournament)
        self.assertEqual(matchups.count(), 14)  # 7 rounds × 2 courts

    def test_first_round_matchups(self):
        """Test that first round matchups follow the correct ranking pattern"""
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

    def test_player_distribution(self):
        """Test that each player plays with and against every other player"""
        tournament = TournamentChart.objects.create(
            name='Test Tournament',
            date='2025-01-01',
            number_of_rounds=7,
            number_of_courts=2
        )
        tournament.players.set(self.players)
        
        self.archetype.generate_matchups(tournament, self.players)
        
        # For each player
        for player in self.players:
            # Get all matchups involving this player
            player_matchups = Matchup.objects.filter(
                tournament_chart=tournament
            ).filter(
                models.Q(pair1_player1=player) |
                models.Q(pair1_player2=player) |
                models.Q(pair2_player1=player) |
                models.Q(pair2_player2=player)
            )
            
            # Should play 7 matches (one per round)
            self.assertEqual(
                player_matchups.count(), 
                7,
                f"Player {player.ranking} plays {player_matchups.count()} matches instead of 7"
            )
            
            # Collect all partners and opponents
            partners = set()
            opponents = set()
            
            for matchup in player_matchups:
                # Determine if player is in team 1 or 2
                if player in [matchup.pair1_player1, matchup.pair1_player2]:
                    # Player is in team 1
                    partners.add(matchup.pair1_player1.ranking)
                    partners.add(matchup.pair1_player2.ranking)
                    opponents.add(matchup.pair2_player1.ranking)
                    opponents.add(matchup.pair2_player2.ranking)
                else:
                    # Player is in team 2
                    partners.add(matchup.pair2_player1.ranking)
                    partners.add(matchup.pair2_player2.ranking)
                    opponents.add(matchup.pair1_player1.ranking)
                    opponents.add(matchup.pair1_player2.ranking)
            
            # Remove player's own ranking from partners
            partners.remove(player.ranking)
            
            # Check variety of partners and opponents
            self.assertTrue(
                len(partners) >= 3,
                f"Player {player.ranking} only plays with {len(partners)} different partners"
            )
            self.assertTrue(
                len(opponents) >= 4,
                f"Player {player.ranking} only plays against {len(opponents)} different opponents"
            )