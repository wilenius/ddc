from dal import autocomplete
from ..models.base_models import Player

class PlayerAutocomplete(autocomplete.Select2QuerySetView):
    def get_queryset(self):
        if not self.request.user.is_authenticated:
            return Player.objects.none()
        qs = Player.objects.all()
        if self.q:
            qs = qs.filter(first_name__icontains=self.q) | qs.filter(last_name__icontains=self.q)
        return qs
