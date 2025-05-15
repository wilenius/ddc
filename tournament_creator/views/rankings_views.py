from django.views.generic import ListView
from django.shortcuts import redirect, render
from django.urls import reverse
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.db.models import Q
from django.core.management import call_command
from django.http import JsonResponse

from tournament_creator.models import Player, RankingsUpdate

class RankingsListView(LoginRequiredMixin, ListView):
    """View to display all player rankings with filtering and sorting."""
    model = Player
    template_name = 'tournament_creator/rankings_list.html'
    context_object_name = 'players'
    paginate_by = 20
    
    def get_queryset(self):
        queryset = Player.objects.all().order_by('ranking')
        
        # Apply division filter if provided
        # Note: This will be expanded when division data is added to Player model
        
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
        try:
            latest_update = RankingsUpdate.objects.filter(successful=True).first()
            context['latest_update'] = latest_update
        except RankingsUpdate.DoesNotExist:
            context['latest_update'] = None
        
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

@login_required
def update_rankings(request):
    """View to manually trigger rankings update."""
    if request.method == 'POST':
        division = request.POST.get('division', 'O')
        
        try:
            # Call the management command to update rankings
            call_command('update_rankings', division=division)
            messages.success(request, f"Rankings successfully updated for {division} division.")
        except Exception as e:
            messages.error(request, f"Error updating rankings: {str(e)}")
            
    # Redirect back to rankings page
    return redirect(reverse('rankings_list') + f'?division={division}')

@login_required
def check_update_status(request):
    """AJAX endpoint to check if new rankings have been imported."""
    try:
        latest_update = RankingsUpdate.objects.filter(successful=True).first()
        if latest_update:
            return JsonResponse({
                'success': True,
                'last_update': latest_update.timestamp.strftime('%Y-%m-%d %H:%M'),
                'division': latest_update.division,
                'player_count': latest_update.player_count
            })
        else:
            return JsonResponse({
                'success': False,
                'message': 'No successful rankings updates found.'
            })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': str(e)
        })