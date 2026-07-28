from django.db.models import Max, Q
from django.views.generic import ListView, CreateView
from django.urls import reverse_lazy
from django.contrib import messages
from ..models.base_models import Player
from ..models.rankings import RankingsUpdate
from ..views.auth import PlayerOrAdminRequiredMixin, SpectatorAccessMixin

class PlayerListView(SpectatorAccessMixin, ListView):
    """
    Displays all players with their ranking and ranking points, with search and
    sorting. Viewable by all logged-in users.
    """
    model = Player
    template_name = 'tournament_creator/player_list.html'
    context_object_name = 'players'
    paginate_by = 20

    def get_queryset(self):
        queryset = Player.objects.all()

        # Apply search filter if provided
        search_query = self.request.GET.get('search', '')
        if search_query:
            queryset = queryset.filter(
                Q(first_name__icontains=search_query) |
                Q(last_name__icontains=search_query)
            )

        # Apply sorting if provided
        sort_by = self.request.GET.get('sort_by', 'ranking')
        if sort_by not in ['ranking', 'first_name', 'last_name', 'ranking_points']:
            sort_by = 'ranking'  # Default sorting

        # Handle reverse sorting
        if self.request.GET.get('sort_order') == 'desc':
            sort_by = f'-{sort_by}'

        return queryset.order_by(sort_by)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Add last update timestamp
        context['latest_update'] = RankingsUpdate.objects.filter(successful=True).first()

        # Add search and sort parameters
        context['search_query'] = self.request.GET.get('search', '')
        context['sort_by'] = self.request.GET.get('sort_by', 'ranking').replace('-', '')
        context['sort_order'] = self.request.GET.get('sort_order', 'asc')
        context['division'] = self.request.GET.get('division', 'O')

        # List available divisions - will be expanded with more divisions later
        context['divisions'] = [
            {'code': 'O', 'name': 'Open'},
            {'code': 'W', 'name': 'Women'},
            {'code': 'M', 'name': 'Mixed'},
            {'code': 'MO', 'name': 'Masters Open'},
            {'code': 'MW', 'name': 'Masters Women'},
        ]

        return context

class PlayerCreateView(PlayerOrAdminRequiredMixin, CreateView):
    """
    Creates a new player. New players start with 0 ranking points and take the
    last spot on the ranking list; a later rankings sync updates both.
    """
    model = Player
    template_name = 'tournament_creator/player_form.html'
    fields = ['first_name', 'last_name']
    success_url = reverse_lazy('player_list')

    def form_valid(self, form):
        last_ranking = Player.objects.aggregate(Max('ranking'))['ranking__max'] or 0
        form.instance.ranking = last_ranking + 1
        form.instance.ranking_points = 0
        messages.success(self.request, "Player created successfully!")
        return super().form_valid(form)
