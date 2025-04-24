from django import forms
from django.utils.translation import gettext_lazy as _

from crispy_forms import bootstrap as twbscrispy
from crispy_forms import layout as crispy
from crispy_forms.helper import FormHelper
from corehq.apps.hqwebapp import crispy as hqcrispy

from corehq.apps.integration.payments.models import MoMoConfig, MoMoEnvironments
from corehq.motech.models import ConnectionSettings


class PaymentConfigureForm(forms.ModelForm):

    class Meta:
        model = MoMoConfig
        fields = [
            'connection_settings',
            'environment',
        ]

    connection_settings = forms.ChoiceField(
        label=_('Connection Settings'),
    )
    environment = forms.ChoiceField(
        label=_('Environment'),
        choices=MoMoEnvironments.choices,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance = kwargs.pop('instance')

        self.fields['connection_settings'].choices = self._get_domain_connection_settings()
        self.helper = FormHelper()
        self.helper.form_tag = False

        self.helper.layout = crispy.Layout(
            crispy.Fieldset(
                _('Payment Configuration'),
                crispy.Field('connection_settings'),
                crispy.Field('environment'),
            ),
            hqcrispy.FormActions(
                twbscrispy.StrictButton(
                    _('Save'),
                    type='submit',
                    css_class='btn btn-primary',
                ),
            )
        )

    def _get_domain_connection_settings(self):
        return ConnectionSettings.objects.filter(
            domain=self.instance.domain
        ).values_list('id', 'name')

    def clean_connection_settings(self):
        connection_settings_id = self.cleaned_data['connection_settings']
        return ConnectionSettings.objects.get(id=connection_settings_id)
