from django.utils.translation import ugettext_lazy as _
from corehq.apps.widget.models import DialerSettings

from corehq.apps.hqwebapp import crispy as hqcrispy
from crispy_forms import layout as crispy
from crispy_forms.layout import Submit

from memoized import memoized
from django import forms


class DialerSettingsForm(forms.ModelForm):
    is_enabled = forms.BooleanField(
        label=_("Enable AWS Connect Dialer"),
        required=False
    )
    url = forms.CharField(
        label=_('AWS Instance ID'),
        help_text=_("""Enter "yourinstance" if your AWS Connect account is 
                        "https://yourinstance.awsapps.com/connect/" """)
    )

    class Meta:
        model = DialerSettings
        fields = [
            'url',
        ]

    def __init__(self, data, *args, **kwargs):
        self._domain = kwargs.pop('domain')
        kwargs['initial'] = self.initial_data
        super(DialerSettingsForm, self).__init__(data, *args, **kwargs)

        self.helper = hqcrispy.HQFormHelper()
        self.helper.form_method = 'POST'
        self.helper.layout = crispy.Layout(
            hqcrispy.B3MultiField(
                _("Telephony Services"),
                hqcrispy.InlineField(
                    'is_enabled', data_bind="checked: isEnabled"
                ),
            ),
            crispy.Div(
                crispy.Field('url', data_bind="value: url"),
                data_bind="visible: isEnabled"
            ),
            hqcrispy.FormActions(
                crispy.ButtonHolder(
                    Submit('submit', _("Update"))
                )
            )
        )

    @property
    @memoized
    def _existing_config(self):
        existing, _created = DialerSettings.objects.get_or_create(
            domain=self._domain,
        )
        return existing

    @property
    def initial_data(self):
        return {
            'is_enabled': self._existing_config.is_enabled,
            'url': self._existing_config.url,
        }

    def save(self):
        self._existing_config.is_enabled = self.cleaned_data['is_enabled']
        self._existing_config.url = self.cleaned_data['url']
        self._existing_config.save()
