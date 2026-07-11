"""ddc URL Configuration"""
from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views

from tournament_creator.views.auth_views import signup

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('tournament_creator.urls')),
    path('login/', auth_views.LoginView.as_view(), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('signup/', signup, name='signup'),
    # Password reset via admin-generated link (no email backend needed). The
    # request/done views are intentionally omitted; directors mint the link
    # from the admin and share it over Signal.
    path('reset/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(
        template_name='registration/password_reset_confirm.html',
        success_url='/reset/done/',
    ), name='password_reset_confirm'),
    path('reset/done/', auth_views.PasswordResetCompleteView.as_view(
        template_name='registration/password_reset_complete.html',
    ), name='password_reset_complete'),
    path('password-change/', auth_views.PasswordChangeView.as_view(
        template_name='tournament_creator/password_change.html',
        success_url='/password-change/done/'
    ), name='password_change'),
    path('password-change/done/', auth_views.PasswordChangeDoneView.as_view(
        template_name='tournament_creator/password_change_done.html'
    ), name='password_change_done'),
]