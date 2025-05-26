import smtplib # Still useful for SMTPException
from django.core.mail import send_mail
from django.core.mail.backends.smtp import EmailBackend as SMTPEmailBackend
from django.conf import settings
from tournament_creator.models.notifications import NotificationBackendSetting, NotificationLog
from tournament_creator.models.auth import User
# from tournament_creator.models.logging import MatchResultLog # For type hinting if needed

def get_player_name(player):
    return str(player) if player else "Unknown Player"

def send_email_notification(user_who_recorded: User, match_result_log_instance):
    """
    Sends an email notification based on a match result log using custom SMTP settings
    from NotificationBackendSetting.
    """
    email_backend_setting = None
    try:
        email_backend_setting = NotificationBackendSetting.objects.get(backend_name='email', is_active=True)
    except NotificationBackendSetting.DoesNotExist:
        NotificationLog.objects.create(
            backend_setting=None,
            success=False,
            details="Email backend 'email' not found or is not active.",
            match_result_log=match_result_log_instance
        )
        return
    except Exception as e:
        NotificationLog.objects.create(
            backend_setting=None,
            success=False,
            details=f"Error fetching email backend settings: {str(e)}",
            match_result_log=match_result_log_instance
        )
        return

    config = email_backend_setting.config
    if not config:
        NotificationLog.objects.create(
            backend_setting=email_backend_setting,
            success=False,
            details="Email backend 'email' is active but has no configuration.",
            match_result_log=match_result_log_instance
        )
        return

    recipient_list_str = config.get('recipient_list')
    from_email = config.get('from_email', settings.DEFAULT_FROM_EMAIL) # Use Django's default if not in config
    
    actual_recipient_list = []
    if isinstance(recipient_list_str, str) and recipient_list_str.strip():
        actual_recipient_list = [email.strip() for email in recipient_list_str.split(',') if email.strip()]
    elif isinstance(recipient_list_str, list): # Robustness for unexpected format
        actual_recipient_list = [str(email).strip() for email in recipient_list_str if str(email).strip()]

    if not actual_recipient_list:
        NotificationLog.objects.create(
            backend_setting=email_backend_setting,
            success=False,
            details="Failed to send email: No recipients found in configuration after parsing or recipient_list is empty.",
            match_result_log=match_result_log_instance
        )
        return

    # SMTP connection parameters from config
    host = config.get('host')
    port = config.get('port')
    username = config.get('username')
    password = config.get('password')
    use_tls = config.get('use_tls', False)
    use_ssl = config.get('use_ssl', False)

    if not host or port is None: # Basic validation for SMTP server settings
        NotificationLog.objects.create(
            backend_setting=email_backend_setting,
            success=False,
            details="Email backend 'email' configuration is missing 'host' or 'port'.",
            match_result_log=match_result_log_instance
        )
        return

    # Construct email content
    tournament_name = match_result_log_instance.matchup.tournament_chart.name
    subject = f"Match Result Update - {tournament_name}"

    matchup = match_result_log_instance.matchup
    team1_display = "Team 1"
    team2_display = "Team 2"

    if matchup.pair1: # Standard Pairs tournament
        team1_display = str(matchup.pair1)
        team2_display = str(matchup.pair2) if matchup.pair2 else "Unknown Opponent"
    elif matchup.pair1_player1: # MoC style tournament
        p1_name = get_player_name(matchup.pair1_player1)
        p2_name = get_player_name(matchup.pair1_player2)
        team1_display = f"{p1_name} & {p2_name}"
        
        p3_name = get_player_name(matchup.pair2_player1)
        p4_name = get_player_name(matchup.pair2_player2)
        team2_display = f"{p3_name} & {p4_name}"
    
    matchup_str = f"{team1_display} vs {team2_display} (Round {matchup.round_number}, Court {matchup.court_number})"

    scores_data = match_result_log_instance.details
    team1_scores_str = ", ".join(map(str, scores_data.get('team1_scores', [])))
    team2_scores_str = ", ".join(map(str, scores_data.get('team2_scores', [])))
    winning_team_declared = scores_data.get('winning_team', 'N/A')
    
    scores_formatted_str = (
        f"  Team 1 Scores: {team1_scores_str}\n"
        f"  Team 2 Scores: {team2_scores_str}\n"
        f"  Declared Winner: {winning_team_declared}"
    )

    message_body = (
        f"A match result was {match_result_log_instance.action.lower()} "
        f"by {user_who_recorded.username}.\n\n"
        f"Tournament: {tournament_name}\n"
        f"Matchup: {matchup_str}\n"
        f"Action: {match_result_log_instance.action}\n"
        f"Scores Reported:\n{scores_formatted_str}\n\n"
        f"Raw Score Details: {scores_data}"
    )

    try:
        # Create a custom EmailBackend instance with settings from config
        custom_email_backend = SMTPEmailBackend(
            host=host,
            port=port,
            username=username,
            password=password,
            use_tls=use_tls,
            use_ssl=use_ssl,
            fail_silently=False # We want to catch exceptions
        )

        num_sent = send_mail(
            subject=subject,
            message=message_body,
            from_email=from_email,
            recipient_list=actual_recipient_list, # Use parsed list
            auth_user=username, # Redundant if using custom_email_backend properly
            auth_password=password, # Redundant if using custom_email_backend properly
            connection=custom_email_backend
        )

        if num_sent > 0:
            NotificationLog.objects.create(
                backend_setting=email_backend_setting,
                success=True,
                details=f"Email successfully sent to: {', '.join(actual_recipient_list)}", # Use parsed list
                match_result_log=match_result_log_instance
            )
        else: # Should not happen if fail_silently=False and no exception
            NotificationLog.objects.create(
                backend_setting=email_backend_setting,
                success=False,
                details="send_mail returned 0 but did not raise an exception.",
                match_result_log=match_result_log_instance
            )
            
    except smtplib.SMTPException as e: # Catch specific SMTP errors
        NotificationLog.objects.create(
            backend_setting=email_backend_setting,
            success=False,
            details=f"SMTP Error: {str(e)}",
            match_result_log=match_result_log_instance
        )
    except Exception as e: # Catch any other errors during email sending
        NotificationLog.objects.create(
            backend_setting=email_backend_setting,
            success=False,
            details=f"Failed to send email: {str(e)}",
            match_result_log=match_result_log_instance
        )
