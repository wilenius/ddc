from django.db import models
from .base_models import TournamentChart

class TournamentStructure(models.Model):
    """
    Base class for different tournament structures
    """
    class Meta:
        abstract = True

    def validate_players(self, players):
        """
        Validate that the players meet the tournament requirements.
        """
        if not players:
            raise ValueError("No players provided")
        return True

    def validate_rankings(self, players):
        """
        Validate that player rankings are appropriate for the tournament.
        """
        rankings = [p.ranking for p in players]
        if len(rankings) != len(set(rankings)):
            raise ValueError("Players must have unique rankings")
        if not all(isinstance(r, int) and r > 0 for r in rankings):
            raise ValueError("All players must have valid positive rankings")
        return True

    def calculate_rounds(self, num_players):
        """
        Calculate number of rounds needed.
        """
        raise NotImplementedError("Subclasses must implement calculate_rounds")

    def calculate_courts(self, num_players):
        """
        Calculate number of courts needed.
        """
        raise NotImplementedError("Subclasses must implement calculate_courts")

    def generate_matchups(self, tournament_chart, players):
        """
        Generate matchups for the tournament.
        """
        raise NotImplementedError("Subclasses must implement generate_matchups")

class PoolStage(TournamentStructure):
    """
    Represents a pool stage in a tournament
    """
    number_of_pools = models.IntegerField()
    players_per_pool = models.IntegerField()
    qualifying_places = models.IntegerField()
    
    def assign_pools(self, players):
        """
        Assign players to pools based on rankings
        """
        raise NotImplementedError("Subclasses must implement pool assignment")

class KnockoutStage(TournamentStructure):
    """
    Represents a knockout stage in a tournament
    """
    number_of_players = models.IntegerField()
    seeded_positions = models.IntegerField(default=0)

    def create_bracket(self, players):
        """
        Create a knockout bracket
        """
        raise NotImplementedError("Subclasses must implement bracket creation")

class RoundRobinStage(TournamentStructure):
    """
    Represents a round-robin stage where everyone plays against everyone
    """
    def generate_schedule(self, players):
        """
        Generate a round-robin schedule
        """
        raise NotImplementedError("Subclasses must implement schedule generation")

class SwissSystemStage(TournamentStructure):
    """
    Represents a Swiss-system tournament stage
    """
    number_of_rounds = models.IntegerField()
    
    def pair_next_round(self, tournament_chart, previous_results):
        """
        Generate pairings for the next round based on current standings
        """
        raise NotImplementedError("Subclasses must implement Swiss pairing")

class KingOfTheCourtStage(TournamentStructure):
    """
    Base class for King of the Court tournament formats
    """
    def validate_rankings(self, players):
        """
        Ensure all players have valid rankings for KoC format
        """
        super().validate_rankings(players)
        rankings = sorted(p.ranking for p in players)
        expected_rankings = list(range(1, len(players) + 1))
        if rankings != expected_rankings:
            raise ValueError(
                f"Players must have consecutive rankings from 1 to {len(players)}"
            )
        return True

class MultiStageStructure:
    """
    Mixin for tournaments with multiple stages
    """
    def get_current_stage(self):
        raise NotImplementedError("Subclasses must implement current stage tracking")
    
    def advance_to_next_stage(self):
        raise NotImplementedError("Subclasses must implement stage advancement")
    
    def get_qualified_players(self):
        raise NotImplementedError("Subclasses must implement qualification rules")