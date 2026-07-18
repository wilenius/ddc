import json
from datetime import date, timedelta

from django.contrib.admin.sites import AdminSite
from django.contrib.auth.tokens import default_token_generator
from django.test import RequestFactory, TestCase, Client, override_settings
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from ..admin import CustomUserAdmin, UserChangeAdminForm
from ..models import Player, User


@override_settings(SIGNUP_INVITE_CODE='ddc4eva', SIGNUP_INVITE_CODE_EXPIRES=date(2026, 7, 31))
class SignupTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.url = reverse('signup')
        self.unlinked = Player.objects.create(
            first_name='Riku', last_name='Aro', ranking=9999, ranking_points=0
        )
        # A player already claimed by another account.
        taken_user = User.objects.create_user(username='taken', password='x')
        self.linked = Player.objects.create(
            first_name='Markus', last_name='Nora', ranking=9998, ranking_points=0,
            user=taken_user,
        )

    def _post(self, **overrides):
        data = {
            'invite_code': 'ddc4eva',
            'player': self.unlinked.pk,
            'username': 'riku',
            'password1': 'sup3rsecret!',
            'password2': 'sup3rsecret!',
        }
        data.update(overrides)
        return self.client.post(self.url, data)

    def test_valid_signup_creates_linked_player_user(self):
        resp = self._post()
        self.assertRedirects(resp, reverse('tournament_list'))
        user = User.objects.get(username='riku')
        self.assertEqual(user.role, User.Role.PLAYER)
        self.unlinked.refresh_from_db()
        self.assertEqual(self.unlinked.user, user)

    def test_wrong_invite_code_rejected(self):
        resp = self._post(invite_code='nope')
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(User.objects.filter(username='riku').exists())
        self.assertContains(resp, 'Invalid invite code')

    def test_expired_code_rejected(self):
        with override_settings(SIGNUP_INVITE_CODE_EXPIRES=date.today() - timedelta(days=1)):
            resp = self._post()
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(User.objects.filter(username='riku').exists())
        self.assertContains(resp, 'Signup has closed')

    def test_dropdown_excludes_linked_players(self):
        resp = self.client.get(self.url)
        players = resp.context['form'].fields['player'].queryset
        self.assertIn(self.unlinked, players)
        self.assertNotIn(self.linked, players)

    def test_duplicate_username_rejected(self):
        resp = self._post(username='taken')
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'already taken')

    def test_weak_password_rejected(self):
        resp = self._post(password1='123', password2='123')
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(User.objects.filter(username='riku').exists())

    def test_authenticated_user_redirected(self):
        self.client.force_login(User.objects.create_user(username='someone', password='x'))
        resp = self.client.get(self.url)
        self.assertRedirects(resp, reverse('tournament_list'))


class PasswordResetLinkTests(TestCase):
    def test_admin_generated_link_sets_password(self):
        user = User.objects.create_user(username='resetme', password='oldpass123')
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)
        url = reverse('password_reset_confirm', kwargs={'uidb64': uid, 'token': token})

        client = Client()
        # First GET redirects to the token-hidden 'set-password' URL.
        resp = client.get(url, follow=True)
        resp = client.post(resp.redirect_chain[-1][0] if resp.redirect_chain else url, {
            'new_password1': 'brandNewPass!9',
            'new_password2': 'brandNewPass!9',
        })
        self.assertEqual(resp.status_code, 302)
        user.refresh_from_db()
        self.assertTrue(user.check_password('brandNewPass!9'))


class AdminLinkTests(TestCase):
    """The User change form links/reassigns/unlinks the reverse Player.user."""

    def setUp(self):
        self.admin = CustomUserAdmin(User, AdminSite())
        self.request = RequestFactory().post('/admin/')
        self.user = User.objects.create_user(username='acct', password='x')
        self.p1 = Player.objects.create(first_name='A', last_name='One', ranking=1)
        self.p2 = Player.objects.create(first_name='B', last_name='Two', ranking=2)

    def _save(self, player):
        form = UserChangeAdminForm(instance=self.user)
        form.cleaned_data = {'player': player}
        self.admin.save_model(self.request, self.user, form, change=True)

    def test_link(self):
        self._save(self.p1)
        self.p1.refresh_from_db()
        self.assertEqual(self.p1.user, self.user)

    def test_reassign_clears_previous(self):
        self._save(self.p1)
        self._save(self.p2)
        self.p1.refresh_from_db()
        self.p2.refresh_from_db()
        self.assertIsNone(self.p1.user)
        self.assertEqual(self.p2.user, self.user)

    def test_unlink(self):
        self._save(self.p1)
        self._save(None)
        self.p1.refresh_from_db()
        self.assertIsNone(self.p1.user)


class LinkablePlayerAutocompleteTests(TestCase):
    """Autocomplete backing the admin 'Linked player' field: staff-only,
    unclaimed players plus the one linked to the user being edited."""

    def setUp(self):
        self.url = reverse('linkable-player-autocomplete')
        self.staff = User.objects.create_user(username='boss', password='x', is_staff=True)
        self.owner = User.objects.create_user(username='owner', password='x')
        self.free = Player.objects.create(first_name='Viktor', last_name='Immonen', ranking=122)
        self.claimed = Player.objects.create(
            first_name='Kristiina', last_name='Hämäläinen', ranking=232, user=self.owner
        )

    def _result_ids(self, resp):
        return [int(r['id']) for r in json.loads(resp.content)['results']]

    def test_requires_staff(self):
        resp = self.client.get(self.url, {'q': 'Immonen'})
        self.assertEqual(self._result_ids(resp), [])
        self.client.force_login(User.objects.create_user(username='pleb', password='x'))
        resp = self.client.get(self.url, {'q': 'Immonen'})
        self.assertEqual(self._result_ids(resp), [])

    def test_searches_last_name_and_excludes_claimed(self):
        self.client.force_login(self.staff)
        resp = self.client.get(self.url, {'q': 'Immonen'})
        self.assertEqual(self._result_ids(resp), [self.free.pk])
        resp = self.client.get(self.url, {'q': 'Hämäläinen'})
        self.assertEqual(self._result_ids(resp), [])

    def test_forwarded_user_keeps_own_linked_player(self):
        self.client.force_login(self.staff)
        resp = self.client.get(self.url, {
            'q': 'Hämäläinen',
            'forward': json.dumps({'for_user': self.owner.pk}),
        })
        self.assertEqual(self._result_ids(resp), [self.claimed.pk])
