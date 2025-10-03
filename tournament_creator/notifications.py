import smtplib # Still useful for SMTPException
from django.core.mail import send_mail
from django.core.mail.backends.smtp import EmailBackend as SMTPEmailBackend
from django.core.cache import cache
import json
import requests
from django.conf import settings
from tournament_creator.models.base_models import TournamentChart # Added import
from tournament_creator.models.notifications import NotificationBackendSetting, NotificationLog
from tournament_creator.models.auth import User
# from tournament_creator.models.logging import MatchResultLog # For type hinting if needed

def get_signal_groups(force_refresh=False):
    """
    Fetch available Signal groups from the API and cache them permanently.
    Use force_refresh=True to bypass cache and fetch fresh data.
    Returns a list of dicts with 'id', 'name', and other group info.
    Raises exceptions on errors for proper error reporting.
    """
    # Check cache first unless force refresh
    if not force_refresh:
        cached_groups = cache.get('signal_groups')
        if cached_groups is not None:
            return cached_groups

    # Get Signal backend settings - will raise DoesNotExist if not found
    signal_backend = NotificationBackendSetting.objects.get(backend_name='signal', is_active=True)
    config = signal_backend.config
    if not config:
        raise ValueError("Signal backend has no configuration")

    signal_cli_rest_api_url = config.get('signal_cli_rest_api_url')
    signal_sender_phone_number = config.get('signal_sender_phone_number')

    if not signal_cli_rest_api_url or not signal_sender_phone_number:
        raise ValueError("Signal CLI URL or sender phone number not configured")

    # Fetch groups from API - will raise RequestException if fails
    groups_url = f"{signal_cli_rest_api_url.rstrip('/')}/v1/groups/{signal_sender_phone_number}"
    response = requests.get(groups_url, timeout=10)
    response.raise_for_status()

    groups_data = response.json()

    # Cache permanently (None = no expiration)
    cache.set('signal_groups', groups_data, None)

    return groups_data

def get_player_name(player, tournament=None):
    """
    Get player name for display, respecting tournament name display preference.
    Args:
        player: Player instance
        tournament: TournamentChart instance (optional)
    Returns:
        str: Player name formatted according to tournament preference
    """
    if not player:
        return "Unknown Player"

    # If no tournament specified or tournament uses first names
    if not tournament or tournament.name_display_format == 'FIRST':
        # Use first names with disambiguation (same logic as get_display_name)
        if tournament:
            all_players = list(tournament.players.all())
            return player.get_display_name(all_players)
        else:
            # No tournament context, just return first name
            return player.first_name

    # Otherwise use last names with disambiguation
    all_players = list(tournament.players.all())
    return player.get_display_name_last_name_mode(all_players)

def send_email_notification(user_who_recorded: User, match_result_log_instance, tournament_chart_instance: TournamentChart):
    """
    Sends an email notification based on a match result log using custom SMTP settings
    from NotificationBackendSetting. Checks both global and per-tournament notification settings.
    """
    # Check per-tournament setting FIRST - if disabled, don't even try to fetch backend
    if not tournament_chart_instance.notify_by_email:
        return  # Silently skip if email notifications disabled for this tournament

    email_backend_setting = None
    try:
        # Check global setting
        email_backend_setting = NotificationBackendSetting.objects.get(backend_name='email', is_active=True)
    except NotificationBackendSetting.DoesNotExist:
        NotificationLog.objects.create(
            backend_setting=None, # No active global backend found
            success=False,
            details="Email backend 'email' not found or is not active globally.",
            match_result_log=match_result_log_instance
        )
        return
    except Exception as e: # Other errors fetching settings
        NotificationLog.objects.create(
            backend_setting=None,
            success=False,
            details=f"Error fetching email backend settings: {str(e)}",
            match_result_log=match_result_log_instance
        )
        return

    config = email_backend_setting.config
    if not config: # Should ideally not happen if active, but good to check
        NotificationLog.objects.create(
            backend_setting=email_backend_setting,
            success=False,
            details="Email backend 'email' is active but has no configuration.",
            match_result_log=match_result_log_instance
        )
        return

    # Proceed with sending email if all checks passed
    recipient_list_str = config.get('recipient_list')
    from_email = config.get('from_email', settings.DEFAULT_FROM_EMAIL)
    
    actual_recipient_list = []
    if isinstance(recipient_list_str, str) and recipient_list_str.strip():
        actual_recipient_list = [email.strip() for email in recipient_list_str.split(',') if email.strip()]
    elif isinstance(recipient_list_str, list):
        actual_recipient_list = [str(email).strip() for email in recipient_list_str if str(email).strip()]

    if not actual_recipient_list:
        NotificationLog.objects.create(
            backend_setting=email_backend_setting,
            success=False,
            details="Failed to send email: No recipients found in configuration after parsing or recipient_list is empty.",
            match_result_log=match_result_log_instance
        )
        return

    host = config.get('host')
    port = config.get('port')
    username = config.get('username')
    password = config.get('password')
    use_tls = config.get('use_tls', False)
    use_ssl = config.get('use_ssl', False)

    if not host or port is None:
        NotificationLog.objects.create(
            backend_setting=email_backend_setting,
            success=False,
            details="Email backend 'email' configuration is missing 'host' or 'port'.",
            match_result_log=match_result_log_instance
        )
        return

    tournament_name = match_result_log_instance.matchup.tournament_chart.name
    subject = f"Match Result Update - {tournament_name}"

    matchup = match_result_log_instance.matchup
    team1_display = "Team 1"
    team2_display = "Team 2"

    if matchup.pair1:
        team1_display = str(matchup.pair1)
        team2_display = str(matchup.pair2) if matchup.pair2 else "Unknown Opponent"
    elif matchup.pair1_player1:
        p1_name = get_player_name(matchup.pair1_player1, tournament_chart_instance)
        p2_name = get_player_name(matchup.pair1_player2, tournament_chart_instance)
        team1_display = f"{p1_name} & {p2_name}"

        p3_name = get_player_name(matchup.pair2_player1, tournament_chart_instance)
        p4_name = get_player_name(matchup.pair2_player2, tournament_chart_instance)
        team2_display = f"{p3_name} & {p4_name}"
    
    matchup_str = f"{team1_display} vs {team2_display} (Round {matchup.round_number}, Court {matchup.court_number})"

    scores_data = match_result_log_instance.details
    team1_scores = scores_data.get('team1_scores', [])
    team2_scores = scores_data.get('team2_scores', [])

    # Format scores as "21-15" or "21-15, 18-21, 15-13" for multiple sets
    score_pairs = []
    for t1_score, t2_score in zip(team1_scores, team2_scores):
        score_pairs.append(f"{t1_score}–{t2_score}")
    scores_str = ", ".join(score_pairs) if score_pairs else "No scores"

    # Format team names according to tournament preference
    if matchup.pair1:
        team1_compact = str(matchup.pair1)
        team2_compact = str(matchup.pair2) if matchup.pair2 else "Unknown"
    elif matchup.pair1_player1:
        team1_compact = f"{get_player_name(matchup.pair1_player1, tournament_chart_instance)} & {get_player_name(matchup.pair1_player2, tournament_chart_instance)}"
        team2_compact = f"{get_player_name(matchup.pair2_player1, tournament_chart_instance)} & {get_player_name(matchup.pair2_player2, tournament_chart_instance)}"
    else:
        team1_compact = "Team 1"
        team2_compact = "Team 2"

    # Compact match result line
    result_line = f"{team1_compact} {scores_str} {team2_compact}"

    action_text = match_result_log_instance.action.lower()

    message_body = (
        f"Match result {action_text} – {tournament_name}\n"
        f"Round {matchup.round_number}, Court {matchup.court_number}\n"
        f"{result_line}\n"
        f"(by {user_who_recorded.username})"
    )

    try:
        custom_email_backend = SMTPEmailBackend(
            host=host, port=port, username=username, password=password,
            use_tls=use_tls, use_ssl=use_ssl, fail_silently=False
        )
        num_sent = send_mail(
            subject=subject, message=message_body, from_email=from_email,
            recipient_list=actual_recipient_list, connection=custom_email_backend
        )
        if num_sent > 0:
            NotificationLog.objects.create(
                backend_setting=email_backend_setting, success=True,
                details=f"Email successfully sent to: {', '.join(actual_recipient_list)}",
                match_result_log=match_result_log_instance
            )
        else:
            NotificationLog.objects.create(
                backend_setting=email_backend_setting, success=False,
                details="send_mail returned 0 but did not raise an exception.",
                match_result_log=match_result_log_instance
            )
    except smtplib.SMTPException as e:
        NotificationLog.objects.create(
            backend_setting=email_backend_setting, success=False,
            details=f"SMTP Error: {str(e)}", match_result_log=match_result_log_instance
        )
    except Exception as e:
        NotificationLog.objects.create(
            backend_setting=email_backend_setting, success=False,
            details=f"Failed to send email: {str(e)}", match_result_log=match_result_log_instance
        )

def send_signal_notification(user_who_recorded: User, match_result_log_instance, tournament_chart_instance: TournamentChart):
    """
    Sends a Signal notification based on a match result log using settings
    from NotificationBackendSetting. Checks both global and per-tournament notification settings.
    """
    # Check per-tournament setting FIRST - if disabled, don't even try to fetch backend
    if not tournament_chart_instance.notify_by_signal:
        return  # Silently skip if Signal notifications disabled for this tournament

    signal_backend_setting = None
    try:
        # Check global setting
        signal_backend_setting = NotificationBackendSetting.objects.get(backend_name='signal', is_active=True)
    except NotificationBackendSetting.DoesNotExist:
        NotificationLog.objects.create(
            backend_setting=None, # No active global backend found
            success=False,
            details="Signal backend 'signal' not found or is not active globally.",
            match_result_log=match_result_log_instance
        )
        return
    except Exception as e: # Other errors fetching settings
        NotificationLog.objects.create(
            backend_setting=None,
            success=False,
            details=f"Error fetching Signal backend settings: {str(e)}",
            match_result_log=match_result_log_instance
        )
        return

    config = signal_backend_setting.config
    if not config: # Should ideally not happen if active, but good to check
        NotificationLog.objects.create(
            backend_setting=signal_backend_setting,
            success=False,
            details="Signal backend 'signal' is active but has no configuration.",
            match_result_log=match_result_log_instance
        )
        return

    # Proceed with sending Signal message if all checks passed
    signal_cli_rest_api_url = config.get('signal_cli_rest_api_url')
    signal_sender_phone_number = config.get('signal_sender_phone_number')

    if not signal_cli_rest_api_url or not signal_sender_phone_number:
        NotificationLog.objects.create(
            backend_setting=signal_backend_setting, success=False,
            details="Signal backend 'signal' configuration is missing 'signal_cli_rest_api_url' or 'signal_sender_phone_number'.",
            match_result_log=match_result_log_instance
        )
        return

    # Check for per-tournament recipients first, fall back to global settings
    recipient_usernames_str = tournament_chart_instance.signal_recipient_usernames.strip() if tournament_chart_instance.signal_recipient_usernames else ''
    recipient_group_ids_str = tournament_chart_instance.signal_recipient_group_ids.strip() if tournament_chart_instance.signal_recipient_group_ids else ''

    # If no per-tournament recipients, use global settings
    if not recipient_usernames_str and not recipient_group_ids_str:
        recipient_usernames_str = config.get('recipient_usernames', '')
        recipient_group_ids_str = config.get('recipient_group_ids', '')

    actual_recipient_usernames = []
    if isinstance(recipient_usernames_str, str) and recipient_usernames_str.strip():
        actual_recipient_usernames = [name.strip() for name in recipient_usernames_str.split(',') if name.strip()]
    elif isinstance(recipient_usernames_str, list):
        actual_recipient_usernames = [str(name).strip() for name in recipient_usernames_str if str(name).strip()]

    actual_recipient_group_ids = []
    if isinstance(recipient_group_ids_str, str) and recipient_group_ids_str.strip():
        actual_recipient_group_ids = [gid.strip() for gid in recipient_group_ids_str.split(',') if gid.strip()]
    elif isinstance(recipient_group_ids_str, list):
        actual_recipient_group_ids = [str(gid).strip() for gid in recipient_group_ids_str if str(gid).strip()]

    if not actual_recipient_usernames and not actual_recipient_group_ids:
        NotificationLog.objects.create(
            backend_setting=signal_backend_setting, success=False,
            details="Failed to send Signal message: No recipient usernames or group IDs found in tournament-specific or global configuration.",
            match_result_log=match_result_log_instance
        )
        return

    tournament_name = match_result_log_instance.matchup.tournament_chart.name
    matchup = match_result_log_instance.matchup
    team1_display = "Team 1"
    team2_display = "Team 2"

    if matchup.pair1:
        team1_display = str(matchup.pair1)
        team2_display = str(matchup.pair2) if matchup.pair2 else "Unknown Opponent"
    elif matchup.pair1_player1:
        p1_name = get_player_name(matchup.pair1_player1, tournament_chart_instance)
        p2_name = get_player_name(matchup.pair1_player2, tournament_chart_instance)
        team1_display = f"{p1_name} & {p2_name}"
        p3_name = get_player_name(matchup.pair2_player1, tournament_chart_instance)
        p4_name = get_player_name(matchup.pair2_player2, tournament_chart_instance)
        team2_display = f"{p3_name} & {p4_name}"
    
    matchup_str = f"{team1_display} vs {team2_display} (Round {matchup.round_number}, Court {matchup.court_number})"

    scores_data = match_result_log_instance.details
    team1_scores = scores_data.get('team1_scores', [])
    team2_scores = scores_data.get('team2_scores', [])

    # Format scores as "21-15" or "21-15, 18-21, 15-13" for multiple sets
    score_pairs = []
    for t1_score, t2_score in zip(team1_scores, team2_scores):
        score_pairs.append(f"{t1_score}–{t2_score}")
    scores_str = ", ".join(score_pairs) if score_pairs else "No scores"

    # Format team names according to tournament preference
    if matchup.pair1:
        team1_compact = str(matchup.pair1)
        team2_compact = str(matchup.pair2) if matchup.pair2 else "Unknown"
    elif matchup.pair1_player1:
        team1_compact = f"{get_player_name(matchup.pair1_player1, tournament_chart_instance)} & {get_player_name(matchup.pair1_player2, tournament_chart_instance)}"
        team2_compact = f"{get_player_name(matchup.pair2_player1, tournament_chart_instance)} & {get_player_name(matchup.pair2_player2, tournament_chart_instance)}"
    else:
        team1_compact = "Team 1"
        team2_compact = "Team 2"

    # Compact match result line
    result_line = f"{team1_compact} {scores_str} {team2_compact}"

    action_text = match_result_log_instance.action.lower()

    message_body = (
        f"Match result {action_text} – {tournament_name}\n"
        f"Round {matchup.round_number}, Court {matchup.court_number}\n"
        f"{result_line}\n"
        f"(by {user_who_recorded.username})"
    )

    payload = {
        "number": signal_sender_phone_number,
        "message": message_body
    }

    # Combine usernames and group IDs into a single recipients list
    all_recipients = []
    if actual_recipient_usernames:
        all_recipients.extend(actual_recipient_usernames)
    if actual_recipient_group_ids:
        all_recipients.extend(actual_recipient_group_ids)

    if all_recipients:
        payload["recipients"] = all_recipients
        
    send_url = f"{signal_cli_rest_api_url.rstrip('/')}/v2/send"
    
    try:
        response = requests.post(send_url, json=payload, timeout=10)
        response.raise_for_status()
        log_details = f"Signal message sent. API Response: {response.status_code} - {response.text}"
        if actual_recipient_usernames:
            log_details += f" Usernames: {', '.join(actual_recipient_usernames)}."
        if actual_recipient_group_ids:
            log_details += f" Group IDs: {', '.join(actual_recipient_group_ids)}."
        NotificationLog.objects.create(
            backend_setting=signal_backend_setting, success=True,
            details=log_details, match_result_log=match_result_log_instance
        )
    except requests.exceptions.HTTPError as e:
        error_details = f"Signal API HTTP Error: {e.response.status_code} - {e.response.text}"
        try:
            error_json = e.response.json()
            if 'error' in error_json:
                 error_details += f" | API Error Message: {error_json['error']}"
        except ValueError:
            pass
        NotificationLog.objects.create(
            backend_setting=signal_backend_setting, success=False,
            details=error_details, match_result_log=match_result_log_instance
        )
    except requests.exceptions.RequestException as e:
        NotificationLog.objects.create(
            backend_setting=signal_backend_setting, success=False,
            details=f"Failed to send Signal message due to a request exception: {str(e)}",
            match_result_log=match_result_log_instance
        )
    except Exception as e:
        NotificationLog.objects.create(
            backend_setting=signal_backend_setting, success=False,
            details=f"An unexpected error occurred while sending Signal message: {str(e)}",
            match_result_log=match_result_log_instance
        )
