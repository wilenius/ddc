"""Tests for tournament location metadata and per-tournament director rights."""
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone

from ..forms import TournamentCreationForm
from ..models import Player, TournamentChart, TournamentDirector, User


class LocationMetadataTests(TestCase):
    """Place and country are mandatory, and unknown spellings need confirming."""

    def setUp(self):
        self.client = Client()
        self.creator = User.objects.create_user(
            username='creator', password='test123', role=User.Role.TOURNAMENT_CREATOR
        )
        self.players = [
            Player.objects.create(first_name=f'P{i}', last_name='Test', ranking=i)
            for i in range(1, 6)
        ]
        # An existing tournament establishes Helsinki/Finland as known values.
        self.existing = TournamentChart.objects.create(
            name='Existing', place='Helsinki', country='Finland',
            date=timezone.now().date(), number_of_rounds=7, number_of_courts=2,
        )
        self.client.login(username='creator', password='test123')

    def _create_data(self, **overrides):
        data = {
            'name': 'New Tournament',
            'place': 'Helsinki',
            'country': 'Finland',
            'date': timezone.now().date(),
            'tournament_category': 'MOC',
            'number_of_stages': 1,
            'format_type': 'STANDARD',
            'name_display_format': 'FIRST',
            'players': [p.id for p in self.players],
        }
        data.update(overrides)
        return data

    def test_location_is_required(self):
        response = self.client.post(reverse('tournament_create'), self._create_data(place='', country=''))
        self.assertEqual(response.status_code, 200)  # re-rendered with errors
        self.assertFormError(response.context['form'], 'place', 'This field is required.')
        self.assertFormError(response.context['form'], 'country', 'This field is required.')

    def test_known_location_creates_directly(self):
        response = self.client.post(reverse('tournament_create'), self._create_data())
        self.assertEqual(response.status_code, 302)
        tournament = TournamentChart.objects.get(name='New Tournament')
        self.assertEqual(tournament.place, 'Helsinki')
        self.assertEqual(tournament.country, 'Finland')
        self.assertEqual(tournament.location, 'Helsinki, Finland')

    def test_unknown_place_needs_confirmation_and_suggests_the_likely_typo(self):
        response = self.client.post(reverse('tournament_create'), self._create_data(place='Hlsinki'))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(TournamentChart.objects.filter(name='New Tournament').exists())
        unconfirmed = response.context['form'].unconfirmed_location
        self.assertEqual([item['value'] for item in unconfirmed], ['Hlsinki'])
        self.assertEqual(unconfirmed[0]['suggestion'], 'Helsinki')

    def test_confirmed_new_location_is_created(self):
        data = self._create_data(
            place='Tampere', country='Finland',
            confirm_new_location=TournamentCreationForm.location_token('Tampere', 'Finland'),
        )
        response = self.client.post(reverse('tournament_create'), data)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(TournamentChart.objects.get(name='New Tournament').place, 'Tampere')

    def test_confirmation_does_not_carry_over_to_an_edited_location(self):
        """A confirmation applies to the values it was given for, not to a later typo."""
        data = self._create_data(
            place='Tmpere', country='Finland',
            confirm_new_location=TournamentCreationForm.location_token('Tampere', 'Finland'),
        )
        response = self.client.post(reverse('tournament_create'), data)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(TournamentChart.objects.filter(name='New Tournament').exists())
        self.assertEqual(
            [item['value'] for item in response.context['form'].unconfirmed_location], ['Tmpere'])

    def test_unknown_country_needs_confirmation_too(self):
        response = self.client.post(reverse('tournament_create'), self._create_data(country='Grmany'))
        self.assertEqual(response.status_code, 200)
        values = [item['value'] for item in response.context['form'].unconfirmed_location]
        self.assertIn('Grmany', values)


class LocationFilterTests(TestCase):
    """The tournament list can be narrowed to a country and/or a place."""

    def setUp(self):
        self.client = Client()
        User.objects.create_user(username='viewer', password='test123', role=User.Role.SPECTATOR)
        today = timezone.now().date()
        for name, place, country in [
            ('Helsinki Open', 'Helsinki', 'Finland'),
            ('Tampere Open', 'Tampere', 'Finland'),
            ('Berlin Open', 'Berlin', 'Germany'),
        ]:
            TournamentChart.objects.create(
                name=name, place=place, country=country,
                date=today, number_of_rounds=7, number_of_courts=2,
            )
        self.client.login(username='viewer', password='test123')

    def test_unfiltered_list_shows_everything(self):
        response = self.client.get(reverse('tournament_list'))
        self.assertEqual(len(response.context['tournaments']), 3)
        self.assertFalse(response.context['location_filter_active'])

    def test_filter_by_country(self):
        response = self.client.get(reverse('tournament_list'), {'country': 'Finland'})
        names = {t.name for t in response.context['tournaments']}
        self.assertEqual(names, {'Helsinki Open', 'Tampere Open'})
        self.assertTrue(response.context['location_filter_active'])

    def test_filter_by_place(self):
        response = self.client.get(reverse('tournament_list'), {'place': 'Berlin'})
        names = {t.name for t in response.context['tournaments']}
        self.assertEqual(names, {'Berlin Open'})

    def test_place_options_follow_the_selected_country(self):
        response = self.client.get(reverse('tournament_list'), {'country': 'Germany'})
        places = {option['value'] for option in response.context['place_options']}
        self.assertEqual(places, {'Berlin'})
        countries = {option['value'] for option in response.context['country_options']}
        self.assertEqual(countries, {'Finland', 'Germany'})

    def test_filter_options_carry_counts(self):
        response = self.client.get(reverse('tournament_list'))
        counts = {option['value']: option['count'] for option in response.context['country_options']}
        self.assertEqual(counts, {'Finland': 2, 'Germany': 1})


class TournamentCreatorRoleTests(TestCase):
    """Only tournament creators and global admins can create tournaments."""

    def setUp(self):
        self.client = Client()
        self.players = [
            Player.objects.create(first_name=f'P{i}', last_name='Test', ranking=i)
            for i in range(1, 6)
        ]
        self.data = {
            'name': 'Role Test Tournament',
            'place': 'Helsinki',
            'country': 'Finland',
            'date': timezone.now().date(),
            'tournament_category': 'MOC',
            'number_of_stages': 1,
            'format_type': 'STANDARD',
            'name_display_format': 'FIRST',
            'confirm_new_location': TournamentCreationForm.location_token('Helsinki', 'Finland'),
            'players': [p.id for p in self.players],
        }

    def _post_as(self, role):
        User.objects.create_user(username=f'user_{role}', password='test123', role=role)
        self.client.login(username=f'user_{role}', password='test123')
        return self.client.post(reverse('tournament_create'), self.data)

    def test_spectator_cannot_create(self):
        self.assertEqual(self._post_as(User.Role.SPECTATOR).status_code, 403)

    def test_plain_player_cannot_create(self):
        self.assertEqual(self._post_as(User.Role.PLAYER).status_code, 403)

    def test_tournament_creator_can_create(self):
        self.assertEqual(self._post_as(User.Role.TOURNAMENT_CREATOR).status_code, 302)

    def test_admin_can_create(self):
        self.assertEqual(self._post_as(User.Role.ADMIN).status_code, 302)

    def test_creator_is_recorded_on_the_tournament(self):
        self._post_as(User.Role.TOURNAMENT_CREATOR)
        tournament = TournamentChart.objects.get(name='Role Test Tournament')
        self.assertEqual(tournament.created_by.username, f'user_{User.Role.TOURNAMENT_CREATOR}')
        self.assertTrue(tournament.user_can_administer(tournament.created_by))


class DirectorRightsTests(TestCase):
    """Director rights are per tournament, not global."""

    def setUp(self):
        self.client = Client()
        self.admin = User.objects.create_user(username='admin', password='test123', role=User.Role.ADMIN)
        self.creator = User.objects.create_user(username='creator', password='test123', role=User.Role.TOURNAMENT_CREATOR)
        self.other_creator = User.objects.create_user(username='other', password='test123', role=User.Role.TOURNAMENT_CREATOR)
        self.helper = User.objects.create_user(username='helper', password='test123', role=User.Role.PLAYER)
        # Only accounts linked to a ranking player can be appointed directors.
        Player.objects.create(first_name='Helper', last_name='Person', ranking=1, user=self.helper)

        self.tournament = TournamentChart.objects.create(
            name='Owned Tournament', place='Helsinki', country='Finland',
            date=timezone.now().date(), number_of_rounds=7, number_of_courts=2,
            created_by=self.creator,
        )

    def test_creator_administers_only_their_own_tournament(self):
        self.assertTrue(self.tournament.user_can_administer(self.creator))
        self.assertFalse(self.tournament.user_can_administer(self.other_creator))
        self.assertTrue(self.tournament.user_can_administer(self.admin))

    def test_appointed_director_gains_rights(self):
        self.assertFalse(self.tournament.user_can_administer(self.helper))
        TournamentDirector.objects.create(
            tournament=self.tournament, user=self.helper, added_by=self.creator
        )
        self.assertTrue(self.tournament.user_can_administer(self.helper))
        # ...but not over someone else's tournament.
        other = TournamentChart.objects.create(
            name='Other', place='Helsinki', country='Finland',
            date=timezone.now().date(), number_of_rounds=7, number_of_courts=2,
            created_by=self.other_creator,
        )
        self.assertFalse(other.user_can_administer(self.helper))

    def test_creator_can_add_and_remove_directors(self):
        url = reverse('tournament_directors', kwargs={'tournament_id': self.tournament.id})
        self.client.login(username='creator', password='test123')

        response = self.client.post(url, {'user': self.helper.id})
        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            TournamentDirector.objects.filter(tournament=self.tournament, user=self.helper).exists()
        )
        self.assertEqual(
            TournamentDirector.objects.get(tournament=self.tournament, user=self.helper).added_by,
            self.creator,
        )

        response = self.client.post(url, {'remove_user': self.helper.id})
        self.assertEqual(response.status_code, 302)
        self.assertFalse(
            TournamentDirector.objects.filter(tournament=self.tournament, user=self.helper).exists()
        )

    def test_appointed_director_can_appoint_further_directors(self):
        TournamentDirector.objects.create(tournament=self.tournament, user=self.helper)
        second = User.objects.create_user(username='second', password='test123', role=User.Role.PLAYER)
        Player.objects.create(first_name='Second', last_name='Person', ranking=2, user=second)

        self.client.login(username='helper', password='test123')
        response = self.client.post(
            reverse('tournament_directors', kwargs={'tournament_id': self.tournament.id}),
            {'user': second.id},
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            TournamentDirector.objects.filter(tournament=self.tournament, user=second).exists()
        )

    def test_outsider_cannot_open_or_change_the_director_list(self):
        url = reverse('tournament_directors', kwargs={'tournament_id': self.tournament.id})
        self.client.login(username='other', password='test123')

        response = self.client.get(url)
        self.assertRedirects(response, reverse('tournament_detail', kwargs={'pk': self.tournament.pk}))

        response = self.client.post(url, {'user': self.helper.id})
        self.assertFalse(
            TournamentDirector.objects.filter(tournament=self.tournament, user=self.helper).exists()
        )

    def test_only_player_linked_accounts_are_offered_as_directors(self):
        self.client.login(username='creator', password='test123')
        response = self.client.get(
            reverse('tournament_directors', kwargs={'tournament_id': self.tournament.id})
        )
        offered = set(response.context['form'].fields['user'].queryset)
        self.assertEqual(offered, {self.helper})

    def test_delete_is_limited_to_this_tournaments_directors(self):
        url = reverse('tournament_delete', kwargs={'pk': self.tournament.pk})

        self.client.login(username='other', password='test123')
        self.assertEqual(self.client.post(url).status_code, 403)

        self.client.login(username='creator', password='test123')
        self.assertEqual(self.client.post(url).status_code, 302)
        self.assertFalse(TournamentChart.objects.filter(pk=self.tournament.pk).exists())

    def test_tiebreak_resolution_is_limited_to_this_tournaments_directors(self):
        url = reverse('manual_tiebreak_resolution', kwargs={'tournament_id': self.tournament.id})

        self.client.login(username='other', password='test123')
        response = self.client.get(url)
        self.assertRedirects(response, reverse('tournament_detail', kwargs={'pk': self.tournament.pk}))

        self.client.login(username='creator', password='test123')
        self.assertEqual(self.client.get(url).status_code, 200)

    def test_directors_may_edit_results_of_past_tournaments(self):
        from datetime import timedelta
        self.tournament.date = timezone.now().date() - timedelta(days=3)
        self.tournament.save()
        self.assertTrue(self.tournament.user_can_edit_results(self.creator))
        self.assertFalse(self.tournament.user_can_edit_results(self.other_creator))
