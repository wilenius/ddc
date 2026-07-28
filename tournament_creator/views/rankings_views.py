from django.shortcuts import redirect
from django.urls import reverse
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.management import call_command
from django.http import JsonResponse

from tournament_creator.models import RankingsUpdate

@login_required
def update_rankings(request):
    """View to manually trigger rankings update."""
    division = 'O'
    if request.method == 'POST':
        division = request.POST.get('division', 'O')

        try:
            # Call the management command to update rankings
            call_command('update_rankings', division=division)
            messages.success(request, f"Rankings successfully updated for {division} division.")
        except Exception as e:
            messages.error(request, f"Error updating rankings: {str(e)}")

    # Redirect back to the players page
    return redirect(reverse('player_list') + f'?division={division}')

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
