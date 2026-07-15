"""
Stress-test concurrent match-result recording through the real production stack.

Unlike simulate_scores (which writes via the ORM in-process), this command drives
score recording over HTTP — nginx → gunicorn → sqlite → notifications — with N
simulated scorers submitting at the same instant, which is the load pattern
expected at a tournament with many courts.

Typical use against the euros test bed (tournament 14):

    python manage.py stress_test_recording 14 --concurrency 5 --enable-signal

Afterwards, restore the test bed with:

    python manage.py simulate_scores 14 --clear

A throwaway login (stress_test_bot, random password, Spectator role) is created
for the run and deleted afterwards.
"""

import json
import secrets
import statistics
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import requests
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.urls import reverse
from django.utils import timezone

from tournament_creator.models.base_models import TournamentChart, Matchup
from tournament_creator.models.notifications import NotificationLog

TEST_USERNAME = 'stress_test_bot'


class Command(BaseCommand):
    help = ('Fire N concurrent score recordings at the running server over HTTP '
            'and report latencies and notification outcomes.')

    def add_arguments(self, parser):
        parser.add_argument('tournament_id', type=int, help='TournamentChart id')
        parser.add_argument('--concurrency', type=int, default=5,
                            help='Number of simultaneous scorers (default 5)')
        parser.add_argument('--base-url', default='https://ddc.hw.iki.fi',
                            help='Base URL of the running server')
        parser.add_argument('--points', type=int, default=15,
                            help='Winning score to submit (default 15)')
        parser.add_argument('--enable-signal', action='store_true',
                            help='Enable notify_by_signal on the tournament for this run '
                                 '(restored afterwards). Sends real Signal messages!')
        parser.add_argument('--wait-notifications', type=float, default=20.0,
                            help='Seconds to wait for notification log entries (default 20)')

    def handle(self, *args, **options):
        tournament = TournamentChart.objects.filter(pk=options['tournament_id']).first()
        if not tournament:
            raise CommandError(f"Tournament {options['tournament_id']} not found")
        base_url = options['base_url'].rstrip('/')
        concurrency = options['concurrency']
        points = options['points']

        matchups = self._pick_matchups(tournament, concurrency)
        self.stdout.write(f"Target: {tournament.name} — matchups "
                          f"{', '.join(str(m.id) for m in matchups)} via {base_url}")

        original_notify = tournament.notify_by_signal
        if options['enable_signal'] and not original_notify:
            tournament.notify_by_signal = True
            tournament.save(update_fields=['notify_by_signal'])
            self.stdout.write(self.style.WARNING(
                'notify_by_signal enabled for this run — real Signal messages will be sent'))
        elif not tournament.notify_by_signal:
            self.stdout.write(self.style.WARNING(
                'notify_by_signal is OFF for this tournament — this run measures plain '
                'recording only. Use --enable-signal to include Signal sends.'))

        password = secrets.token_urlsafe(16)
        user = self._create_test_user(password)
        started_at = timezone.now()
        try:
            sessions = [self._login(base_url, TEST_USERNAME, password)
                        for _ in range(concurrency)]
            results = self._fire(base_url, sessions, matchups, points, tournament)
        finally:
            user.delete()
            if options['enable_signal'] and not original_notify:
                tournament.notify_by_signal = original_notify
                tournament.save(update_fields=['notify_by_signal'])

        self._report(results)
        if tournament.notify_by_signal or options['enable_signal']:
            self._report_notifications(started_at, len(matchups),
                                       options['wait_notifications'])
        self.stdout.write(f"\nRestore the test bed with: "
                          f"python manage.py simulate_scores {tournament.pk} --clear")

    def _pick_matchups(self, tournament, count):
        matchups = list(
            Matchup.objects.filter(tournament_chart=tournament, scores__isnull=True)
            .order_by('round_number', 'court_number')[:count]
        )
        if len(matchups) < count:
            # Fall back to re-recording already-scored matchups; the write path
            # (delete + recreate scores, logs, notifications) is identical.
            self.stdout.write(self.style.WARNING(
                f'Only {len(matchups)} unscored matchups — reusing scored ones for the rest'))
            extra = (Matchup.objects.filter(tournament_chart=tournament)
                     .exclude(pk__in=[m.pk for m in matchups])
                     .order_by('round_number', 'court_number')[:count - len(matchups)])
            matchups += list(extra)
        if len(matchups) < count:
            raise CommandError(f'Tournament has only {len(matchups)} matchups')
        return matchups

    def _create_test_user(self, password):
        User = get_user_model()
        User.objects.filter(username=TEST_USERNAME).delete()
        return User.objects.create_user(
            username=TEST_USERNAME, password=password, role=User.Role.SPECTATOR)

    def _login(self, base_url, username, password):
        session = requests.Session()
        login_url = f'{base_url}/login/'
        resp = session.get(login_url, timeout=10)
        resp.raise_for_status()
        resp = session.post(
            login_url,
            data={'username': username, 'password': password,
                  'csrfmiddlewaretoken': session.cookies['csrftoken']},
            headers={'Referer': login_url},
            timeout=10,
        )
        if 'sessionid' not in session.cookies:
            raise CommandError(f'Login failed (HTTP {resp.status_code})')
        return session

    def _fire(self, base_url, sessions, matchups, points, tournament):
        barrier = threading.Barrier(len(matchups))
        results = []

        def record(session, matchup):
            path = reverse('record_match_result', args=[tournament.pk, matchup.pk])
            data = {
                'team1_scores': json.dumps([points]),
                'team2_scores': json.dumps([max(points - 2, 0)]),
                # Skip the warn-and-confirm format check; generated scores
                # don't necessarily match the tournament's game structure.
                'confirmed': '1',
                'csrfmiddlewaretoken': session.cookies['csrftoken'],
            }
            barrier.wait()
            t0 = time.perf_counter()
            try:
                resp = session.post(f'{base_url}{path}', data=data,
                                    headers={'Referer': f'{base_url}{path}'}, timeout=60)
                elapsed = time.perf_counter() - t0
                try:
                    status = resp.json().get('status', '?')
                except ValueError:
                    status = f'non-JSON response (HTTP {resp.status_code})'
                return (matchup.pk, resp.status_code, status, elapsed)
            except requests.RequestException as e:
                return (matchup.pk, None, f'request error: {e}',
                        time.perf_counter() - t0)

        with ThreadPoolExecutor(max_workers=len(matchups)) as pool:
            futures = [pool.submit(record, s, m) for s, m in zip(sessions, matchups)]
            results = [f.result() for f in futures]
        return results

    def _report(self, results):
        self.stdout.write('\n=== Recording results ===')
        latencies = []
        for matchup_id, http_status, status, elapsed in sorted(results, key=lambda r: r[3]):
            ok = http_status == 200 and status == 'success'
            style = self.style.SUCCESS if ok else self.style.ERROR
            self.stdout.write(style(
                f'matchup {matchup_id}: HTTP {http_status} / {status} in {elapsed:.2f}s'))
            latencies.append(elapsed)
        self.stdout.write(f'latency min/median/max: {min(latencies):.2f}s / '
                          f'{statistics.median(latencies):.2f}s / {max(latencies):.2f}s')

    def _report_notifications(self, started_at, expected, wait_seconds):
        self.stdout.write('\n=== Signal notifications (from NotificationLog) ===')
        deadline = time.monotonic() + wait_seconds
        logs = []
        while time.monotonic() < deadline:
            logs = list(NotificationLog.objects.filter(
                timestamp__gte=started_at,
                backend_setting__backend_name='signal').order_by('timestamp'))
            if len(logs) >= expected:
                break
            time.sleep(1)
        for log in logs:
            style = self.style.SUCCESS if log.success else self.style.ERROR
            self.stdout.write(style(f'{log.timestamp:%H:%M:%S} success={log.success} '
                                    f'{log.details[:120]}'))
        if len(logs) < expected:
            self.stdout.write(self.style.WARNING(
                f'Only {len(logs)}/{expected} signal notification logs appeared within '
                f'{wait_seconds:.0f}s — check that gunicorn was restarted with the async '
                f'notification code and the signal backend is active.'))
