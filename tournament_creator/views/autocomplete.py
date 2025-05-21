from dal import autocomplete
from django.db.models import Q
from django.http import JsonResponse
import logging
from ..models.base_models import Player

logger = logging.getLogger(__name__)

class PlayerAutocomplete(autocomplete.Select2QuerySetView):
    def get_queryset(self):
        # Log authentication status and request details
        logger.info("User authenticated: %s", self.request.user.is_authenticated)
        logger.info("Request headers: %s", self.request.headers)
        logger.info("Query parameters: %s", self.request.GET)
        
        if not self.request.user.is_authenticated:
            logger.warning("Unauthenticated user trying to access player autocomplete")
            return Player.objects.none()
        
        qs = Player.objects.all()
        logger.info("Total players in database: %d", qs.count())
        
        # Filter out already selected players
        selected_player_ids = self.request.GET.getlist('selected')
        if selected_player_ids:
            logger.info("Excluding %d already selected players", len(selected_player_ids))
            qs = qs.exclude(id__in=selected_player_ids)
            
        if self.q:
            logger.info("Search query: %s", self.q)
            qs = qs.filter(Q(first_name__icontains=self.q) | Q(last_name__icontains=self.q))
            logger.info("Filtered players count: %d", qs.count())
        else:
            # Return an initial set of players even without a search query
            logger.info("No search query, returning first 20 players")
            qs = qs.order_by('last_name', 'first_name')[:20]
        
        return qs
    
    def get(self, request, *args, **kwargs):
        """Override to add more detailed logging"""
        try:
            result = super().get(request, *args, **kwargs)
            logger.info("Autocomplete result status: %s", result.status_code)
            try:
                import json
                result_data = json.loads(result.content.decode('utf-8'))
                logger.info("Autocomplete result count: %d", len(result_data.get('results', [])))
                logger.info("Autocomplete result: %s", result_data)
            except Exception as e:
                logger.error("Error parsing autocomplete result: %s", e)
            return result
        except Exception as e:
            logger.error("Error in autocomplete get: %s", e)
            raise
