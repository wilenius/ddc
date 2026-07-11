from datetime import date

from django import forms
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.utils.safestring import mark_safe
from dal import autocomplete
from .models.base_models import Player, TournamentChart
from .models.notifications import NotificationBackendSetting # Added import

class TournamentCreationForm(forms.ModelForm):
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
            'name', 'date', 'end_date', 'number_of_stages', 'format_type',
            'notify_by_email', 'notify_by_signal', 'notify_by_matrix',
            'signal_recipient_usernames', 'signal_recipient_group_ids',
            'name_display_format', 'show_structure', 'default_sets_per_match',
            'archived'
        ]
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., Summer League 2025'}),
            'notify_by_email': forms.CheckboxInput,
            'notify_by_signal': forms.CheckboxInput,
            'notify_by_matrix': forms.CheckboxInput,
            'date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control', 'style': 'max-width: 200px;'}),
            'end_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control', 'style': 'max-width: 200px;'}),
            'number_of_stages': forms.NumberInput(attrs={'class': 'form-control', 'style': 'width: 60px;', 'min': '1', 'max': '9'}),
            'format_type': forms.Select(attrs={'class': 'form-select'}),
            'name_display_format': forms.Select(attrs={'class': 'form-select'}),
            'default_sets_per_match': forms.Select(attrs={'class': 'form-select', 'style': 'width: 80px;'}),
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
            'date': 'Start Date',
            'end_date': 'End Date',
            'number_of_stages': 'Stages',
            'format_type': 'Format',
            'name_display_format': 'Player Names',
            'default_sets_per_match': 'Sets per match',
        }
        help_texts = {
            'name': '',
            'number_of_stages': '',
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
