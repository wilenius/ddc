from django.http import JsonResponse
from django.contrib.admin.views.decorators import staff_member_required
from ..notifications import get_signal_groups


@staff_member_required
def refresh_signal_groups(request):
    """
    Refresh the cached Signal groups from the API.
    Only accessible to admin/staff users.
    """
    try:
        groups = get_signal_groups(force_refresh=True)
        return JsonResponse({
            'success': True,
            'count': len(groups),
            'groups': groups
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)
