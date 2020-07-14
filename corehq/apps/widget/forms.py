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
    aws_instance_id = forms.CharField(
        label=_('AWS Instance ID'),
        help_text=_("""Enter "yourinstance" if your AWS Connect account is
                        "https://yourinstance.awsapps.com/connect/" """)
    )

    dialer_page_header = forms.CharField(
        label=_('Dialer Page Title'),
        help_text=_("A title for the Dialer Page header")
    )
    dialer_page_subheader = forms.CharField(
        label=_('Dialer Page Subtitle'),
        help_text=_("A subtitle for the Dialer Page header")
    )

    class Meta:
        model = DialerSettings
        fields = [
            'aws_instance_id',
            'dialer_page_header',
            'dialer_page_subheader'
        ]

    def __init__(self, data, *args, **kwargs):
        self.domain = kwargs.pop('domain')
        kwargs['initial'] = self.initial_data
        super(DialerSettingsForm, self).__init__(data, *args, **kwargs)

        self.helper = hqcrispy.HQFormHelper()
        self.helper.form_method = 'POST'
        self.helper.layout = crispy.Layout(
            hqcrispy.B3MultiField(
                _("Telephony Services"),
                hqcrispy.InlineField('is_enabled'),
            ),
            crispy.Div(
                crispy.Field('aws_instance_id'),
            ),
            crispy.Div(
                crispy.Field('dialer_page_header'),
            ),
            crispy.Div(
                crispy.Field('dialer_page_subheader'),
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
            domain=self.domain
        )
        return existing

    @property
    def initial_data(self):
        return {
            'is_enabled': self._existing_config.is_enabled,
            'aws_instance_id': self._existing_config.aws_instance_id,
            'dialer_page_header': self._existing_config.dialer_page_header,
            'dialer_page_subheader': self._existing_config.dialer_page_subheader
        }

    def save(self):
        self._existing_config.is_enabled = self.cleaned_data['is_enabled']
        self._existing_config.aws_instance_id = self.cleaned_data['aws_instance_id']
        self._existing_config.dialer_page_header = self.cleaned_data['dialer_page_header']
        self._existing_config.dialer_page_subheader = self.cleaned_data['dialer_page_subheader']
        self._existing_config.save()
