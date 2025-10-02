from django.apps import AppConfig


class TournamentCreatorConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'tournament_creator'
    
    def ready(self):
        # Import models here to ensure they're registered
        from .models.tournament_types import MonarchOfTheCourt8, FourPairsSwedishFormat, EightPairsSwedishFormat

        # Connect signal to populate archetypes after migrations
        from django.db.models.signals import post_migrate
        post_migrate.connect(self._populate_archetypes, sender=self)

    def _populate_archetypes(self, sender, **kwargs):
        """
        Populate tournament archetypes after migrations are complete.
        This runs via post_migrate signal, avoiding database access during app initialization.
        """
        from .models import TournamentArchetype

        # Define archetypes based on get_implementation() mapping in tournament_types.py
        ARCHETYPES = [
            dict(name="4 pairs doubles tournament", description="Round robin: 3 rounds on 2 fields with 4 pairs.", tournament_category="PAIRS"),
            dict(name="8 pairs doubles tournament", description="Round robin: 7 rounds on 4 fields with 8 pairs.", tournament_category="PAIRS"),
            dict(name="5-player Monarch of the Court", description="MoC: 5-player specific schedule (Option A).", tournament_category="MOC"),
            dict(name="6-player Monarch of the Court", description="MoC: 6-player specific schedule (Option A).", tournament_category="MOC"),
            dict(name="7-player Monarch of the Court", description="MoC: 7-player specific schedule.", tournament_category="MOC"),
            dict(name="8-player Monarch of the Court", description="MoC: 8-player specific schedule.", tournament_category="MOC"),
            dict(name="9-player Monarch of the Court", description="MoC: 9-player specific schedule with 2 courts.", tournament_category="MOC"),
            dict(name="10-player Monarch of the Court", description="MoC: 10-player specific schedule with 2 courts.", tournament_category="MOC"),
            dict(name="11-player Monarch of the Court", description="MoC: 11-player specific schedule with 2 courts.", tournament_category="MOC"),
            dict(name="12-player Monarch of the Court", description="MoC: 12-player specific schedule with 3 courts.", tournament_category="MOC"),
            dict(name="13-player Monarch of the Court", description="MoC: 13-player specific schedule with 3 courts.", tournament_category="MOC"),
            dict(name="14-player Monarch of the Court", description="MoC: 14-player specific schedule with 3 courts.", tournament_category="MOC"),
            dict(name="15-player Monarch of the Court", description="MoC: 15-player specific schedule with 3 courts.", tournament_category="MOC"),
            dict(name="16-player Monarch of the Court", description="MoC: 16-player specific schedule with 4 courts.", tournament_category="MOC"),
        ]

        for row in ARCHETYPES:
            TournamentArchetype.objects.get_or_create(
                name=row["name"],
                defaults=row
            )
