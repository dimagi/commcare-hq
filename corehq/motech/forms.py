from django import forms
from django.core.exceptions import ValidationError
from django.utils.translation import ugettext_lazy as _

from crispy_forms import bootstrap as twbscrispy
from crispy_forms import layout as crispy
from crispy_forms.helper import FormHelper

from corehq.motech.models import ConnectionSettings


class ConnectionSettingsForm(forms.ModelForm):
    url = forms.CharField(
        label=_('URL'),
        help_text=_('e.g. "http://play.dhis2.org/demo/"')
    )
    username = forms.CharField(required=False)
    plaintext_password = forms.CharField(
        label=_('Password'),
        required=False,
        widget=forms.PasswordInput,
    )
    skip_cert_verify = forms.BooleanField(
        label=_('Skip certificate verification'),
        help_text=_('Do not use in a production environment'),
        required=False,
    )
    notify_addresses_str = forms.CharField(
        label=_('Addresses to send notifications'),
        help_text=_('A comma-separated list of email addresses to send error '
                    'notifications'),
        required=False,
    )

    class Meta:
        model = ConnectionSettings
        fields = [
            'name',
            'url',
            'auth_type',
            'username',
            'plaintext_password',
            'skip_cert_verify',
            'notify_addresses_str',
        ]

    def __init__(self, *args, domain, **kwargs):
        self.domain = domain  # Passed by ``FormSet.form_kwargs``
        super().__init__(*args, **kwargs)

    def save(self, commit=True):
        self.instance.domain = self.domain
        return super().save(commit)


class BaseConnectionSettingsFormSet(forms.BaseModelFormSet):

    def __init__(self, *args, domain, **kwargs):
        super().__init__(*args, **kwargs)
        self.domain = domain
        self.form_kwargs['domain'] = domain  # Passed by ``FormView.get_form_kwargs()``

    def clean(self):
        super().clean()
        errors = [f'Unable to delete connection "{f.instance}": It is in use.'
                  for f in self.not_deleted_forms]
        if errors:
            raise ValidationError(errors)

    @property
    def not_deleted_forms(self):
        """
        Returns a list of forms marked for deletion but whose
        ConnectionSettings are in use.
        """
        deleted_forms = super().deleted_forms
        ids_in_use = get_connection_ids_in_use(self.domain)
        return [f for f in deleted_forms
                if f.is_bound and f.instance.id in ids_in_use]


def get_connection_ids_in_use(domain):
    from corehq.motech.dhis2.dbaccessors import get_dataset_maps

    dataset_maps = get_dataset_maps(domain)
    # So far only DataSetMaps use ConnectionSettings. When more things
    # do (like Repeaters), this must check those too.
    return {m.connection_settings_id for m in dataset_maps
            if m.connection_settings_id}


ConnectionSettingsFormSet = forms.modelformset_factory(
    model=ConnectionSettings,
    form=ConnectionSettingsForm,
    formset=BaseConnectionSettingsFormSet,
    extra=1,
    can_delete=True,
)


class ConnectionSettingsFormSetHelper(FormHelper):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.form_class = 'form-horizontal'
        self.label_class = 'col-sm-3 col-md-2'
        self.field_class = 'col-sm-9 col-md-8 col-lg-6'
        self.layout = crispy.Layout(
            crispy.Fieldset(
                _('Remote Connection'),
                crispy.Field('name'),
                crispy.Field('url'),
                crispy.Field('auth_type'),
                crispy.Field('username'),
                crispy.Field('plaintext_password'),
                twbscrispy.PrependedText('skip_cert_verify', ''),
                crispy.Field('notify_addresses_str'),
                twbscrispy.PrependedText(
                    'DELETE', '',
                    wrapper_class='alert alert-warning'
                ),
            ),
        )
        self.add_input(
            crispy.Submit('submit', _('Save Connections'))
        )
        self.render_required_fields = True
