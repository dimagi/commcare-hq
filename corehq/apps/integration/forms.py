from django import forms
from django.utils.translation import ugettext as _
from django.utils.translation import ugettext_lazy, ugettext_noop

from crispy_forms import layout as crispy
from crispy_forms.layout import Submit
from memoized import memoized

from corehq.apps.hqwebapp import crispy as hqcrispy
from corehq.apps.integration.models import SimprintsIntegration, DialerSettings


from django.utils.translation import ugettext_lazy as _

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


class SimprintsIntegrationForm(forms.Form):
    is_enabled = forms.BooleanField(
        label=ugettext_noop("Enable Simprints Integration"),
        required=False
    )
    project_id = forms.CharField(
        label=ugettext_noop("Project ID"),
        required=False,
    )
    user_id = forms.CharField(
        label=ugettext_noop("User ID"),
        required=False,
    )
    module_id = forms.CharField(
        label=ugettext_noop("Module ID"),
        required=False,
    )

    def __init__(self, data, *args, **kwargs):
        self._domain = kwargs.pop('domain')
        super(SimprintsIntegrationForm, self).__init__(data, *args, **kwargs)

        self.helper = hqcrispy.HQFormHelper()
        self.helper.form_method = 'POST'
        self.helper.layout = crispy.Layout(
            hqcrispy.B3MultiField(
                _("Simprints Integration"),
                hqcrispy.InlineField(
                    'is_enabled', data_bind="checked: isEnabled"
                ),
            ),
            crispy.Div(
                crispy.Field('project_id', data_bind="value: projectId"),
                crispy.Field('user_id', data_bind="value: userId"),
                crispy.Field('module_id', data_bind="value: moduleId"),
                data_bind="visible: isEnabled"
            ),
            hqcrispy.FormActions(
                crispy.ButtonHolder(
                    Submit('submit', ugettext_lazy("Update"))
                )
            )
        )

    @property
    @memoized
    def _existing_integration(self):
        existing, _created = SimprintsIntegration.objects.get_or_create(
            domain=self._domain,
        )
        return existing

    @property
    def initial_data(self):
        return {
            'is_enabled': self._existing_integration.is_enabled,
            'project_id': self._existing_integration.project_id,
            'user_id': self._existing_integration.user_id or "global_user",
            'module_id': self._existing_integration.module_id or "global_module",
        }

    def save(self):
        self._existing_integration.is_enabled = self.cleaned_data['is_enabled']
        self._existing_integration.project_id = self.cleaned_data['project_id']
        self._existing_integration.user_id = self.cleaned_data['user_id']
        self._existing_integration.module_id = self.cleaned_data['module_id']
        self._existing_integration.save()
