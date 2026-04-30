import json

from django import forms
from django.utils.translation import gettext_lazy as _

from crispy_forms import bootstrap as twbscrispy
from crispy_forms import layout as crispy
from crispy_forms.helper import FormHelper

from corehq.apps.hqwebapp import crispy as hqcrispy
from corehq.apps.integration.payments.models import (
    MoMoConfig,
    MoMoEnvironments,
    MoMoProviders,
)
from corehq.motech.models import ConnectionSettings


class PaymentConfigureForm(forms.ModelForm):

    class Meta:
        model = MoMoConfig
        fields = [
            'provider',
            'connection_settings',
            'environment',
        ]

    provider = forms.ChoiceField(
        label=_('Provider'),
        required=True,
        choices=MoMoProviders.choices,
    )
    connection_settings = forms.ChoiceField(
        label=_('Connection Settings'),
    )
    environment = forms.ChoiceField(
        label=_('Environment'),
        choices=MoMoEnvironments.choices,
        required=False,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance = kwargs.pop('instance')

        self.fields['connection_settings'].choices = self._get_domain_connection_settings()
        self.helper = FormHelper()
        self.helper.form_tag = False

        self.helper.layout = crispy.Layout(
            crispy.Div(
                crispy.Fieldset(
                    _('Payment Configuration'),
                    crispy.Field(
                        'provider',
                        x_init='provider = $el.value',
                        x_model='provider',
                    ),
                    crispy.Field('connection_settings'),
                    crispy.Div(
                        'environment',
                        x_show=f"provider === '{MoMoProviders.MTN_MONEY}'",
                    ),
                ),
                hqcrispy.FormActions(
                    twbscrispy.StrictButton(
                        _('Save'),
                        type='submit',
                        css_class='btn btn-primary',
                    ),
                ),
                x_data=json.dumps({
                    'provider': self.instance.provider,
                }),
            )
        )

    def _get_domain_connection_settings(self):
        return ConnectionSettings.objects.filter(
            domain=self.instance.domain
        ).values_list('id', 'name')

    def clean_connection_settings(self):
        connection_settings_id = self.cleaned_data['connection_settings']
        return ConnectionSettings.objects.get(id=connection_settings_id)

    def clean_environment(self):
        environment = self.cleaned_data.get('environment')
        provider = self.cleaned_data.get('provider')
        if provider == MoMoProviders.ORANGE_CAMEROON_MONEY:
            environment = MoMoEnvironments.LIVE
        return environment
