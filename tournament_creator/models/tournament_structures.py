from django.db import models
from .base_models import TournamentChart
from typing import List, Any

class TournamentStructure(models.Model):
    """
    Base class for different tournament structures. Subclasses must implement specific methods.
    """
    class Meta:
        abstract = True

    def validate_players(self, players: List[Any]) -> bool:
        """
        Validate that the player list meets the tournament requirements.
        Raises exceptions for invalid input.
        """
        if not players:
            raise ValueError("No players provided")
        return True

    def validate_rankings(self, players: List[Any]) -> bool:
        """
        Validate that player rankings are appropriate for the tournament.
        Ensures unique and positive integer rankings.
        """
        rankings = [p.ranking for p in players]
        if len(rankings) != len(set(rankings)):
            raise ValueError("Players must have unique rankings")
        if not all(isinstance(r, int) and r > 0 for r in rankings):
            raise ValueError("All players must have valid positive rankings")
        return True

    def calculate_rounds(self, num_players: int) -> int:
        """
        Calculate number of rounds needed. Subclasses must implement.
        """
        raise NotImplementedError("Subclasses must implement calculate_rounds")

    def calculate_courts(self, num_players: int) -> int:
        """
        Calculate number of courts needed. Subclasses must implement.
        """
        raise NotImplementedError("Subclasses must implement calculate_courts")

    def generate_matchups(self, tournament_chart: TournamentChart, players: List[Any]) -> None:
        """
        Generate matchups for the tournament. Subclasses must implement.
        """
        raise NotImplementedError("Subclasses must implement generate_matchups")

class PoolStage(TournamentStructure):
    """
    Represents a pool stage in a tournament.
    """
    number_of_pools = models.IntegerField()
    players_per_pool = models.IntegerField()
    qualifying_places = models.IntegerField()
    
    def assign_pools(self, players: List[Any]) -> Any:
        """
        Assign players to pools based on rankings. Subclasses must implement.
        """
        raise NotImplementedError("Subclasses must implement pool assignment")

class KnockoutStage(TournamentStructure):
    """
    Represents a knockout stage in a tournament.
    """
    number_of_players = models.IntegerField()
    seeded_positions = models.IntegerField(default=0)

    def create_bracket(self, players: List[Any]) -> Any:
        """
        Create a knockout bracket. Subclasses must implement.
        """
        raise NotImplementedError("Subclasses must implement bracket creation")

class RoundRobinStage(TournamentStructure):
    """
    Represents a round-robin stage where everyone plays everyone.
    """
    def generate_schedule(self, players: List[Any]) -> Any:
        """
        Generate a round-robin schedule. Subclasses must implement.
        """
        raise NotImplementedError("Subclasses must implement schedule generation")

class SwissSystemStage(TournamentStructure):
    """
    Represents a Swiss-system tournament stage.
    """
    number_of_rounds = models.IntegerField()
    
    def pair_next_round(self, tournament_chart: TournamentChart, previous_results: Any) -> Any:
        """
        Generate pairings for the next round based on standings. Subclasses must implement.
        """
        raise NotImplementedError("Subclasses must implement Swiss pairing")

class KingOfTheCourtStage(TournamentStructure):
    """
    Base class for King of the Court tournament formats with stricter ranking validation.
    """
    def validate_rankings(self, players: List[Any]) -> bool:
        """
        Ensure all players have consecutive rankings for KoC format.
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
    Mixin for tournaments with multiple stages, e.g., pool, knockout, finals.
    """
    def get_current_stage(self) -> Any:
        raise NotImplementedError("Subclasses must implement current stage tracking")
    
    def advance_to_next_stage(self) -> None:
        raise NotImplementedError("Subclasses must implement stage advancement")
    
    def get_qualified_players(self) -> Any:
        raise NotImplementedError("Subclasses must implement qualification rules")
