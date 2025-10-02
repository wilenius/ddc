from django import forms
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
            'name', 'date',
            'notify_by_email', 'notify_by_signal', 'notify_by_matrix',
            'signal_recipient_usernames', 'signal_recipient_group_ids'
        ]
        widgets = {
            'notify_by_email': forms.CheckboxInput,
            'notify_by_signal': forms.CheckboxInput,
            'notify_by_matrix': forms.CheckboxInput,
            'date': forms.DateInput(attrs={'type': 'date'}),
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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Make tournament_category not required when editing (only needed during creation)
        if self.instance and self.instance.pk:
            self.fields['tournament_category'].required = False

        # Populate group picker choices from cache
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

        # Pre-select groups if editing existing tournament
        if self.instance and self.instance.pk:
            existing_group_ids = self.instance.signal_recipient_group_ids
            if existing_group_ids:
                selected_ids = [gid.strip() for gid in existing_group_ids.split(',') if gid.strip()]
                picker_ids = [choice[0] for choice in choices]
                picker_selected = [gid for gid in selected_ids if gid in picker_ids]
                self.fields['signal_groups_picker'].initial = picker_selected

                # Also populate the manual field with ALL existing group IDs as backup
                self.fields['signal_recipient_group_ids'].initial = existing_group_ids

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
