from django.apps import AppConfig


class TournamentCreatorConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'tournament_creator'
    
    def ready(self):
        # Import models here to ensure they're registered
        from .models.tournament_types import MonarchOfTheCourt8, FourPairsSwedishFormat, EightPairsSwedishFormat
        
        # Register proxy models with admin if needed
        # You can add any other initialization code here
