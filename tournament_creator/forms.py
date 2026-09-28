from datetime import date

from django import forms
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.utils.safestring import mark_safe
from dal import autocomplete
from .models.base_models import Player, TournamentChart
from .models.tournament_types import (
    DEFAULT_MATCH_RULES, MATCH_RULE_TYPES, PAIRS_FORMAT_OPTIONS, default_cap,
)
from .models.notifications import NotificationBackendSetting # Added import

class TournamentCreationForm(forms.ModelForm):
    # The unknown-location confirmation needs the "create anyway" button of the
    # create page; subclasses rendered elsewhere (Django admin) switch it off.
    require_location_confirmation = True

    SETS_CHOICES = [(1, '1'), (3, '3'), (5, '5')]

    TOURNAMENT_CATEGORY_CHOICES = [
        ('', 'Select a tournament type'),
        ('MOC', 'Monarch of the Court'),
        ('PAIRS', 'Doubles (Pairs)'),
    ]

    tournament_category = forms.ChoiceField(
        choices=TOURNAMENT_CATEGORY_CHOICES,
        required=True,
        label='Tournament Type',
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    # Carries the place/country the director has confirmed as genuinely new (see
    # clean()). It holds a token of the confirmed values rather than a plain flag,
    # so that any resubmit of the warned-about form confirms it — but editing the
    # location afterwards asks again instead of waving a second typo through.
    confirm_new_location = forms.CharField(required=False, widget=forms.HiddenInput)

    # Doubles playing format (tournament_types.PAIRS_FORMAT_OPTIONS). Blank picks the
    # first format that fits the pair count; the view validates it against the count.
    pairs_format = forms.ChoiceField(
        choices=[('', 'Automatic')] + [(o['key'], o['label']) for o in PAIRS_FORMAT_OPTIONS],
        required=False,
        label='Playing format',
        widget=forms.Select(attrs={'class': 'form-select'}),
    )

    # Group picker for tournaments (same as Signal backend, but without refresh button)
    signal_groups_picker = forms.MultipleChoiceField(
        label="Select Signal Groups",
        required=False,
        widget=forms.SelectMultiple(attrs={
            'class': 'form-control',
            'style': 'height: 150px;'
        }),
        help_text='Select Signal groups for notifications (leave empty to use global settings)'
    )

    class Meta:
        model = TournamentChart
        fields = [
            'name', 'short_name', 'place', 'country', 'date', 'end_date', 'format_type',
            'notify_by_email', 'notify_by_signal', 'notify_by_matrix',
            'signal_recipient_usernames', 'signal_recipient_group_ids',
            'name_display_format', 'show_structure', 'default_sets_per_match',
            'archived', 'is_sandbox',
            'uses_signup', 'signup_deadline', 'signup_min', 'signup_max',
            'league_courts', 'league_max_matches_per_day', 'league_back_to_back', 'league_avoid_parallel',
        ]
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., Summer League 2025'}),
            'short_name': forms.TextInput(attrs={'class': 'form-control', 'style': 'max-width: 200px;', 'placeholder': 'e.g., EO26'}),
            'place': forms.TextInput(attrs={
                'class': 'form-control', 'style': 'max-width: 320px;',
                'placeholder': 'e.g., Helsinki', 'list': 'known-places', 'autocomplete': 'off',
            }),
            'country': forms.TextInput(attrs={
                'class': 'form-control', 'style': 'max-width: 320px;',
                'placeholder': 'e.g., Finland', 'list': 'known-countries', 'autocomplete': 'off',
            }),
            'notify_by_email': forms.CheckboxInput,
            'notify_by_signal': forms.CheckboxInput,
            'notify_by_matrix': forms.CheckboxInput,
            'date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control', 'style': 'max-width: 200px;'}),
            'end_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control', 'style': 'max-width: 200px;'}),
            'format_type': forms.Select(attrs={'class': 'form-select'}),
            'name_display_format': forms.Select(attrs={'class': 'form-select'}),
            'default_sets_per_match': forms.Select(attrs={'class': 'form-select', 'style': 'width: 80px;'}),
            'uses_signup': forms.CheckboxInput,
            'signup_deadline': forms.DateTimeInput(
                attrs={'type': 'datetime-local', 'class': 'form-control', 'style': 'max-width: 240px;'},
                format='%Y-%m-%dT%H:%M'),
            'signup_min': forms.NumberInput(attrs={'class': 'form-control', 'style': 'width: 80px;', 'min': 1}),
            'signup_max': forms.NumberInput(attrs={'class': 'form-control', 'style': 'width: 80px;', 'min': 1}),
            'league_courts': forms.NumberInput(attrs={'class': 'form-control', 'style': 'width: 80px;', 'min': 1, 'max': 20}),
            'league_max_matches_per_day': forms.NumberInput(attrs={'class': 'form-control', 'style': 'width: 80px;', 'min': 1}),
            'league_back_to_back': forms.CheckboxInput,
            'league_avoid_parallel': forms.CheckboxInput,
            'signal_recipient_usernames': forms.Textarea(attrs={
                'rows': 2,
                'placeholder': 'Optional: +358401234567, +358409876543 (leave empty to use global settings)',
                'class': 'form-control'
            }),
            'signal_recipient_group_ids': forms.Textarea(attrs={
                'rows': 2,
                'placeholder': 'Optional: Manually enter group IDs or use picker above',
                'class': 'form-control'
            }),
        }
        labels = {
            'place': 'Place',
            'country': 'Country',
            'date': 'Start Date',
            'end_date': 'End Date',
            'format_type': 'Format',
            'name_display_format': 'Player Names',
            'default_sets_per_match': 'Sets per match',
        }
        help_texts = {
            'name': '',
            'place': '',
            'country': '',
            'format_type': '',
            'name_display_format': '',
            'show_structure': '',
            'default_sets_per_match': '',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Set default dates to today for new tournaments
        from datetime import date
        if not self.instance.pk:  # Only for new tournaments
            today = date.today()
            if 'initial' not in kwargs or not kwargs['initial'].get('date'):
                self.fields['date'].initial = today
            if 'initial' not in kwargs or not kwargs['initial'].get('end_date'):
                self.fields['end_date'].initial = today

        # Make tournament_category not required when editing (only needed during creation)
        if self.instance and self.instance.pk and 'tournament_category' in self.fields:
            self.fields['tournament_category'].required = False

        # Field has a model default; let it apply when omitted (e.g., for non-MoC submissions
        # where the field isn't shown in the UI). Guard the access because the admin restricts
        # this form to the fields in its fieldsets, which omit default_sets_per_match.
        if 'default_sets_per_match' in self.fields:
            self.fields['default_sets_per_match'].required = False
        # Only sign-up leagues show the court count; others keep the model default
        if 'league_courts' in self.fields:
            self.fields['league_courts'].required = False

        # Score rules per doubles match type: {type}_points, {type}_cap, {type}_sets,
        # combined into cleaned_data['match_rules'] by clean(). Not model fields, so
        # only the creation page renders them.
        for key, _label in MATCH_RULE_TYPES:
            defaults = DEFAULT_MATCH_RULES[key]
            self.fields[f'{key}_points'] = forms.IntegerField(
                required=False, min_value=1, max_value=99, initial=defaults['points_to'],
                widget=forms.NumberInput(attrs={'class': 'form-control', 'style': 'width: 70px;',
                                                'data-rule-points': key}))
            self.fields[f'{key}_cap'] = forms.IntegerField(
                required=False, min_value=1, max_value=99, initial=defaults['cap'],
                widget=forms.NumberInput(attrs={'class': 'form-control', 'style': 'width: 70px;',
                                                'data-rule-cap': key}))
            self.fields[f'{key}_sets'] = forms.TypedChoiceField(
                required=False, coerce=int, empty_value=None,
                choices=self.SETS_CHOICES, initial=defaults['best_of'],
                widget=forms.Select(attrs={'class': 'form-select', 'style': 'width: 80px;'}))

        # Populate the Signal group picker choices from cache.
        if 'signal_groups_picker' in self.fields:
            from django.core.cache import cache
            groups = cache.get('signal_groups', [])
            choices = []

            if groups:
                for group in groups:
                    group_id = group.get('id', '') or group.get('internal_id', '')
                    group_name = group.get('name') or group.get('title', 'Unnamed Group')
                    if group_id:
                        choices.append((group_id, f"{group_name} ({group_id[:30]}...)"))

            self.fields['signal_groups_picker'].choices = choices
            if not choices:
                self.fields['signal_groups_picker'].help_text = 'No groups available. Configure groups in Signal backend settings first.'

            # Pre-select groups if editing an existing tournament
            if self.instance and self.instance.pk:
                existing_group_ids = self.instance.signal_recipient_group_ids
                if existing_group_ids:
                    selected_ids = [gid.strip() for gid in existing_group_ids.split(',') if gid.strip()]
                    picker_ids = [choice[0] for choice in choices]
                    picker_selected = [gid for gid in selected_ids if gid in picker_ids]
                    self.fields['signal_groups_picker'].initial = picker_selected

                    # Also populate the manual field with ALL existing group IDs as backup
                    if 'signal_recipient_group_ids' in self.fields:
                        self.fields['signal_recipient_group_ids'].initial = existing_group_ids

    def clean_place(self):
        return (self.cleaned_data.get('place') or '').strip()

    def clean_country(self):
        return (self.cleaned_data.get('country') or '').strip()

    def clean(self):
        """Flag places/countries no previous tournament has used.

        Location is free text, so a typo would silently create a new entry in
        the location filter ("Hlsinki"). Unknown values therefore need one
        confirmation click: the warned-about form carries the location back in a
        hidden ``confirm_new_location`` token, so submitting it again — from
        either button — goes through, while a location edited in between is
        checked afresh.
        """
        cleaned = super().clean()
        cleaned['match_rules'] = self._clean_match_rules(cleaned)
        if cleaned.get('uses_signup') and 'tournament_category' in self.fields:
            self._clean_signup(cleaned)
            if cleaned.get('format_type') == 'LEAGUE':
                self._clean_league_slots(cleaned)
        # These two drive the confirm banner and its hidden token in the template.
        self.unconfirmed_location = None
        self.location_confirmation_token = self.location_token(
            cleaned.get('place'), cleaned.get('country'))
        if (not self.require_location_confirmation
                or cleaned.get('confirm_new_location') == self.location_confirmation_token):
            return cleaned

        unknown = []
        for field, label in (('country', 'country'), ('place', 'place')):
            value = cleaned.get(field)
            if not value:
                continue
            if TournamentChart.objects.filter(**{f'{field}__iexact': value}).exists():
                continue
            suggestion = self._closest_known(field, value)
            unknown.append({'field': field, 'label': label, 'value': value, 'suggestion': suggestion})

        if unknown:
            self.unconfirmed_location = unknown
            parts = []
            for item in unknown:
                part = f'No tournaments have previously been created in {item["value"]}'
                if item['suggestion']:
                    part += f' — did you mean {item["suggestion"]}?'
                parts.append(part + '.')
            raise forms.ValidationError(' '.join(parts) + ' Check the spelling, or confirm to create it anyway.')

        return cleaned

    def _clean_match_rules(self, cleaned):
        """Rules of the match types whose points were submitted, keyed by type.
        A blank cap takes the suggested one (default_cap); a blank set count, one set."""
        rules = {}
        for key, label in MATCH_RULE_TYPES:
            points = cleaned.get(f'{key}_points')
            if points is None:
                continue
            cap = cleaned.get(f'{key}_cap') or default_cap(points)
            if cap < points:
                self.add_error(f'{key}_cap', f"{label}: the cap can't be below the points a game is played to.")
                continue
            rules[key] = {'points_to': points, 'cap': cap,
                          'best_of': cleaned.get(f'{key}_sets') or 1}
        return rules

    @staticmethod
    def default_signup_deadline(start_date):
        """Two days before the tournament, at the end of that day (local time)."""
        from datetime import datetime, time, timedelta
        from django.utils import timezone
        return timezone.make_aware(datetime.combine(start_date - timedelta(days=2), time(23, 59)))

    def _clean_signup(self, cleaned):
        """Defaults and bounds of a sign-up tournament's deadline and entry limits.

        The limits count players for MoC and pairs for doubles, bounded by the
        formats that exist for that many entries (signup_entry_counts).
        """
        from .models.tournament_types import signup_entry_counts
        start = cleaned.get('date')
        if cleaned.get('signup_deadline') is None and start:
            cleaned['signup_deadline'] = self.default_signup_deadline(start)
        deadline = cleaned.get('signup_deadline')
        if deadline and start:
            from django.utils import timezone
            if timezone.localtime(deadline).date() > start:
                self.add_error('signup_deadline', "The sign-up deadline can't be after the tournament starts.")

        category = cleaned.get('tournament_category')
        if category not in ('MOC', 'PAIRS'):
            return
        counts = signup_entry_counts(category, cleaned.get('pairs_format') or '')
        if not counts:
            self.add_error(None, "No formats exist for this tournament type.")
            return
        unit = 'players' if category == 'MOC' else 'pairs'
        low, high = counts[0], counts[-1]
        if cleaned.get('signup_min') is None:
            cleaned['signup_min'] = max(4, low)
        if cleaned.get('signup_max') is None:
            cleaned['signup_max'] = high
        minimum, maximum = cleaned['signup_min'], cleaned['signup_max']
        if not low <= minimum <= high:
            self.add_error('signup_min', f"The minimum must be between {low} and {high} {unit}.")
        if not low <= maximum <= high:
            self.add_error('signup_max', f"The maximum must be between {low} and {high} {unit}.")
        if minimum > maximum:
            self.add_error('signup_max', "The maximum can't be below the minimum.")

    def _clean_league_slots(self, cleaned):
        """A sign-up league's time slots, from the day rows of the creation page
        (``slot_date`` and ``slot_times`` lists): cleaned['league_slots'] is a
        sorted list of (date, time)."""
        slots, self.slot_rows = set(), []
        for day_text, times_text in zip(self.data.getlist('slot_date'), self.data.getlist('slot_times')):
            if not day_text.strip() and not times_text.strip():
                continue
            self.slot_rows.append((day_text, times_text))
            try:
                day = date.fromisoformat(day_text.strip())
            except ValueError:
                self.add_error(None, f"Time slots: '{day_text}' isn't a date.")
                continue
            try:
                times = parse_slot_times(times_text)
            except ValueError as e:
                self.add_error(None, f"Time slots on {day:%d.%m.%Y}: {e}")
                continue
            slots.update((day, t) for t in times)
        if not slots and not self.errors:
            self.add_error(None, "Add at least one day with the times matches can be played at.")
        cleaned['league_slots'] = sorted(slots)

    def match_rule_rows(self):
        """Bound fields per match type, for the rules table on the creation page."""
        rows = []
        for key, label in MATCH_RULE_TYPES:
            fields = [self[f'{key}_{part}'] for part in ('points', 'cap', 'sets')]
            rows.append({
                'key': key, 'label': label,
                'points': fields[0], 'cap': fields[1], 'sets': fields[2],
                'errors': [error for field in fields for error in field.errors],
            })
        return rows

    @staticmethod
    def location_token(place, country):
        """Value a confirmation applies to; a changed place or country invalidates it."""
        return '|'.join(((place or '').strip().lower(), (country or '').strip().lower()))

    @staticmethod
    def _closest_known(field, value):
        """Nearest existing value for ``field``, if one is close enough to be a likely typo."""
        import difflib
        known = list(
            TournamentChart.objects.exclude(**{field: ''})
            .values_list(field, flat=True).distinct()
        )
        matches = difflib.get_close_matches(value.lower(), [k.lower() for k in known], n=1, cutoff=0.75)
        if not matches:
            return None
        return next((k for k in known if k.lower() == matches[0]), None)

    def clean_league_courts(self):
        return self.cleaned_data.get('league_courts') or TournamentChart._meta.get_field('league_courts').default

    def clean_default_sets_per_match(self):
        # Fall back to the model's default when empty (the field is hidden for non-MoC).
        value = self.cleaned_data.get('default_sets_per_match')
        if value in (None, ''):
            return TournamentChart._meta.get_field('default_sets_per_match').default
        return value

    def save(self, commit=True):
        instance = super().save(commit=False)

        # Combine group picker selections with manual group IDs
        selected_groups = self.cleaned_data.get('signal_groups_picker', [])
        manual_group_ids = self.cleaned_data.get('signal_recipient_group_ids', '')

        # Combine both sources
        all_group_ids = list(selected_groups)
        if manual_group_ids and manual_group_ids.strip():
            manual_ids = [gid.strip() for gid in manual_group_ids.split(',') if gid.strip()]
            for gid in manual_ids:
                if gid not in all_group_ids:
                    all_group_ids.append(gid)

        # Update the field with combined IDs
        instance.signal_recipient_group_ids = ', '.join(all_group_ids) if all_group_ids else ''

        if commit:
            instance.save()
        return instance

def parse_slot_times(text):
    """Start times from free text such as '18:00, 19.30 20': a sorted list of
    ``datetime.time``. Raises ValueError naming what isn't a time, or if none are given."""
    import re
    from datetime import time
    times = set()
    for token in re.split(r'[\s,;]+', text.strip()):
        if not token:
            continue
        match = re.fullmatch(r'(\d{1,2})(?:[:.](\d{2}))?', token)
        hour, minute = (int(match.group(1)), int(match.group(2) or 0)) if match else (99, 0)
        if hour > 23 or minute > 59:
            raise ValueError(f"'{token}' isn't a time (use e.g. 18:00).")
        times.add(time(hour, minute))
    if not times:
        raise ValueError("give at least one start time.")
    return sorted(times)


class LeagueSettingsForm(forms.ModelForm):
    """A sign-up league's scheduling rules, editable until (and after) scheduling."""
    class Meta:
        model = TournamentChart
        fields = ['league_courts', 'league_max_matches_per_day', 'league_back_to_back', 'league_avoid_parallel']
        widgets = TournamentCreationForm.Meta.widgets

    def clean_league_courts(self):
        courts = self.cleaned_data['league_courts']
        if not courts:
            raise forms.ValidationError("At least one court is needed.")
        return courts


class LeagueDayForm(forms.Form):
    """Add one day's time slots to a sign-up league."""
    date = forms.DateField(widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control', 'style': 'max-width: 200px;'}))
    times = forms.CharField(widget=forms.TextInput(attrs={
        'class': 'form-control', 'style': 'max-width: 320px;', 'placeholder': 'e.g., 18:00, 19:00, 20:00'}))

    def clean_times(self):
        try:
            return parse_slot_times(self.cleaned_data['times'])
        except ValueError as e:
            raise forms.ValidationError(str(e)[0].upper() + str(e)[1:])


class TournamentDirectorAddForm(forms.Form):
    """Appoint another user as director of a single tournament.

    Only accounts linked to a ranking player are offered, so a director always
    has a real identity in the system.
    """
    user = forms.ModelChoiceField(
        queryset=get_user_model().objects.none(),
        label="Add a director",
        empty_label="Select a person…",
        widget=forms.Select(attrs={'class': 'form-select', 'style': 'max-width: 420px;'}),
    )

    def __init__(self, tournament, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.tournament = tournament
        User = get_user_model()
        already = set(tournament.directors.values_list('pk', flat=True))
        if tournament.created_by_id:
            already.add(tournament.created_by_id)
        self.fields['user'].queryset = (
            User.objects.filter(player__isnull=False)
            .exclude(pk__in=already)
            .select_related('player')
            .order_by('player__first_name', 'player__last_name')
        )
        self.fields['user'].label_from_instance = (
            lambda user: f"{user.player.first_name} {user.player.last_name} ({user.username})"
        )


class TournamentSignupForm(forms.Form):
    """An entry to a sign-up tournament.

    Players sign themselves up (``player`` is the viewer's own ranking player);
    directors pick the player too, so they can enter people without an account.
    Doubles entries also name the partner, who needs no account.
    """
    player = forms.ModelChoiceField(
        queryset=Player.objects.all(),
        label="Player",
        empty_label='',
        widget=forms.Select(attrs={'class': 'form-select signup-player-select'}),
    )
    partner = forms.ModelChoiceField(
        queryset=Player.objects.all(),
        label="Partner",
        empty_label='',
        widget=forms.Select(attrs={'class': 'form-select signup-player-select'}),
    )

    def __init__(self, tournament, *args, own_player=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.tournament = tournament
        self.own_player = own_player
        if own_player is not None:
            del self.fields['player']
        if tournament.signup_category != 'PAIRS':
            del self.fields['partner']
        # Only offer players who aren't in yet
        available = Player.objects.exclude(pk__in=self.entered_ids()).order_by('first_name', 'last_name')
        if own_player is not None:
            available = available.exclude(pk=own_player.pk)
        for field in self.fields.values():
            field.queryset = available

    def entered_ids(self):
        """Ids of the players already signed up, as player or partner."""
        signups = self.tournament.signups.all()
        return (set(signups.values_list('player_id', flat=True))
                | set(signups.exclude(partner=None).values_list('partner_id', flat=True)))

    def clean(self):
        cleaned = super().clean()
        player = self.own_player or cleaned.get('player')
        partner = cleaned.get('partner')
        if self.errors or player is None:
            return cleaned
        cleaned['player'] = player
        if partner is not None and partner == player:
            self.add_error('partner', "Pick someone else as your partner." if self.own_player
                           else "Pick two different players.")
            return cleaned

        if self.own_player and self.own_player.pk in self.entered_ids():
            raise forms.ValidationError("You're already signed up.")
        maximum = self.tournament.signup_max
        if maximum and self.tournament.signups.count() >= maximum:
            raise forms.ValidationError("The tournament is full.")
        return cleaned


class PairForm(forms.Form):
    player1 = forms.ModelChoiceField(
        queryset=Player.objects.all(),
        widget=autocomplete.ModelSelect2(url='player-autocomplete')
    )
    player2 = forms.ModelChoiceField(
        queryset=Player.objects.all(),
        widget=autocomplete.ModelSelect2(url='player-autocomplete')
    )
    def clean(self):
        cleaned = super().clean()
        p1 = cleaned.get('player1')
        p2 = cleaned.get('player2')
        if p1 and p2 and p1 == p2:
            self.add_error('player2', 'Choose two different players for each pair!')
        return cleaned

PairFormSet = forms.formset_factory(PairForm, extra=0)

class MoCPlayerSelectForm(forms.Form):
    players = forms.ModelMultipleChoiceField(
        queryset=Player.objects.all(),
        widget=autocomplete.ModelSelect2Multiple(url='player-autocomplete'),
        label="Players"
    )

class EmailBackendConfigForm(forms.ModelForm): # Changed base class
    # Explicitly defined fields remain, these are not derived from the model directly
    # but are intended to populate/read from the 'config' JSONField of the model.
    recipient_list = forms.CharField(
        label="Recipient List",
        help_text="Comma-separated email addresses"
    )
    from_email = forms.EmailField(
        label="From Email"
    )
    host = forms.CharField(
        label="SMTP Host"
    )
    port = forms.IntegerField(
        label="SMTP Port",
        initial=587
    )
    username = forms.CharField(
        label="SMTP Username",
        required=False
    )
    password = forms.CharField(
        label="SMTP Password",
        widget=forms.PasswordInput(render_value=True),
        required=False,
        help_text="Leave blank to keep existing password. Enter a new password to change it."
    )
    use_tls = forms.BooleanField(
        label="Use TLS",
        required=False,
        initial=True
    )
    use_ssl = forms.BooleanField(
        label="Use SSL",
        required=False,
        initial=False
    )

    class Meta:
        model = NotificationBackendSetting
        fields = ['backend_name', 'is_active']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)  # Call ModelForm's __init__

        # Populate custom form fields from instance.config
        # These fields are defined explicitly on the form class (host, port, etc.)
        if self.instance and self.instance.pk and self.instance.backend_name == 'email':
            config = self.instance.config or {}
            
            custom_field_keys = ['recipient_list', 'from_email', 'host', 'port', 'username', 'password', 'use_tls', 'use_ssl']
            
            for field_name in custom_field_keys:
                if field_name in self.fields: # Check field exists on form
                    if field_name == 'password':
                        # For password fields, typically we don't set an initial value
                        # that displays the old password hash or a placeholder like '********'.
                        # The widget's render_value=True was set for the field definition,
                        # so if an initial value IS set, it would show.
                        # By setting initial = None, it will render as empty.
                        # The save_model logic in ModelAdmin will handle preserving old password if field is blank.
                        self.fields[field_name].initial = None
                    else:
                        self.fields[field_name].initial = config.get(field_name)


class SignalBackendConfigForm(forms.ModelForm):
    signal_cli_rest_api_url = forms.URLField(
        label="Signal CLI REST API URL",
        help_text="The base URL of the signal-cli-rest-api service (e.g., http://localhost:8080)."
    )
    signal_sender_phone_number = forms.CharField(
        label="Signal Sender Phone Number",
        help_text="The phone number registered with Signal to send messages from (e.g., +1234567890)."
    )
    recipient_usernames = forms.CharField(
        label="Recipient Usernames (Phone Numbers)",
        widget=forms.Textarea(attrs={'rows': 3}),
        required=False,
        help_text="Comma-separated list of recipient phone numbers (e.g., +1987654321,+1555123456)."
    )

    # Group picker - populated from cache
    recipient_groups_picker = forms.MultipleChoiceField(
        label="Select Groups",
        required=False,
        widget=forms.SelectMultiple(attrs={
            'class': 'form-control',
            'style': 'height: 150px;'
        }),
        help_text=mark_safe('Select groups from the list. <button type="button" id="refresh-groups-btn" class="btn btn-sm btn-secondary">Refresh Groups</button>')
    )

    recipient_group_ids = forms.CharField(
        label="Manual Group IDs (Advanced)",
        widget=forms.Textarea(attrs={'rows': 3}),
        required=False,
        help_text="Manually enter comma-separated group IDs if not available in the picker above."
    )

    class Meta:
        model = NotificationBackendSetting
        fields = ['backend_name', 'is_active'] # Fields from the model

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Always populate group picker choices from cache (needed for both GET and POST/validation)
        from django.core.cache import cache
        groups = cache.get('signal_groups', [])  # Get from cache only, default to empty list
        choices = []

        if groups:
            for group in groups:
                # Extract group info - use 'id' (with group. prefix) not 'internal_id'
                group_id = group.get('id', '') or group.get('internal_id', '')
                group_name = group.get('name') or group.get('title', 'Unnamed Group')
                if group_id:
                    choices.append((group_id, f"{group_name} ({group_id[:30]}...)"))

        self.fields['recipient_groups_picker'].choices = choices
        # Always show the refresh button, update message if no groups
        if not choices:
            self.fields['recipient_groups_picker'].help_text = mark_safe('No groups in cache. <button type="button" id="refresh-groups-btn" class="btn btn-sm btn-secondary">Refresh Groups</button> to load available groups.')
        else:
            self.fields['recipient_groups_picker'].help_text = mark_safe(f'Select groups from the list ({len(choices)} available). <button type="button" id="refresh-groups-btn" class="btn btn-sm btn-secondary">Refresh Groups</button>')

        # Populate custom form fields from instance.config for 'signal' backend (only when editing)
        if self.instance and self.instance.pk and self.instance.backend_name == 'signal':
            config = self.instance.config or {}

            custom_field_keys = [
                'signal_cli_rest_api_url',
                'signal_sender_phone_number',
                'recipient_usernames',
                'recipient_group_ids'
            ]

            for field_name in custom_field_keys:
                if field_name in self.fields: # Check field exists on form
                    self.fields[field_name].initial = config.get(field_name)

            # Pre-select groups that are in recipient_group_ids
            existing_group_ids = config.get('recipient_group_ids', '')
            if existing_group_ids:
                selected_ids = [gid.strip() for gid in existing_group_ids.split(',') if gid.strip()]

                # Try to pre-select IDs that exist in the picker choices
                picker_ids = [choice[0] for choice in choices]
                picker_selected = [gid for gid in selected_ids if gid in picker_ids]
                self.fields['recipient_groups_picker'].initial = picker_selected

                # Put ALL existing group IDs in the manual field as backup
                self.fields['recipient_group_ids'].initial = existing_group_ids


class PlayerSignupForm(forms.Form):
    """
    Self-service signup gated by a shared invite code. Creates a PLAYER user
    and links it to a ranking Player that has no account yet.
    """
    invite_code = forms.CharField(
        label="Invite code",
        widget=forms.TextInput(attrs={'class': 'form-control', 'autocomplete': 'off'}),
        help_text="The code shared in the tournament Signal group.",
    )
    player = forms.ModelChoiceField(
        queryset=Player.objects.none(),
        label="Your name",
        empty_label="Select your name…",
        widget=forms.Select(attrs={'class': 'form-select'}),
        help_text="Pick yourself from the rankings list. Ask a director if you're missing.",
    )
    username = forms.CharField(
        label="Username",
        widget=forms.TextInput(attrs={'class': 'form-control', 'autocomplete': 'username'}),
    )
    password1 = forms.CharField(
        label="Password",
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'autocomplete': 'new-password'}),
    )
    password2 = forms.CharField(
        label="Confirm password",
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'autocomplete': 'new-password'}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Only players without a linked account can be claimed.
        self.fields['player'].queryset = Player.objects.filter(
            user__isnull=True
        ).order_by('ranking')

    def clean_invite_code(self):
        code = self.cleaned_data['invite_code'].strip()
        expected = settings.SIGNUP_INVITE_CODE
        expires = settings.SIGNUP_INVITE_CODE_EXPIRES
        if not expected:
            raise forms.ValidationError("Signup is currently disabled.")
        if expires and date.today() > expires:
            raise forms.ValidationError("Signup has closed for this tournament.")
        if code != expected:
            raise forms.ValidationError("Invalid invite code.")
        return code

    def clean_username(self):
        username = self.cleaned_data['username'].strip()
        User = get_user_model()
        if User.objects.filter(username__iexact=username).exists():
            raise forms.ValidationError("That username is already taken.")
        return username

    def clean_password2(self):
        password1 = self.cleaned_data.get('password1')
        password2 = self.cleaned_data.get('password2')
        if password1 and password2 and password1 != password2:
            raise forms.ValidationError("The two passwords don't match.")
        # Run Django's configured password validators.
        validate_password(password2)
        return password2

    def save(self):
        User = get_user_model()
        user = User.objects.create_user(
            username=self.cleaned_data['username'],
            password=self.cleaned_data['password1'],
            role=User.Role.PLAYER,
        )
        player = self.cleaned_data['player']
        player.user = user
        player.save(update_fields=['user'])
        return user
