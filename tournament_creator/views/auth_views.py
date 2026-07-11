from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.db import transaction
from django.shortcuts import redirect, render

from ..forms import PlayerSignupForm


def signup(request):
    """Invite-code-gated self-service signup that links a new PLAYER account
    to an existing ranking Player."""
    # Already authenticated users have no business signing up.
    if request.user.is_authenticated:
        return redirect('tournament_list')

    if request.method == 'POST':
        form = PlayerSignupForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                user = form.save()
            login(request, user)
            messages.success(
                request,
                "Welcome! Your account is linked to your player profile.",
            )
            return redirect('tournament_list')
    else:
        form = PlayerSignupForm()

    return render(request, 'registration/signup.html', {
        'form': form,
        'signup_enabled': bool(settings.SIGNUP_INVITE_CODE),
    })
