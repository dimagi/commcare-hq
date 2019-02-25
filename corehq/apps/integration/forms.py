from __future__ import absolute_import
from __future__ import unicode_literals

from memoized import memoized
from django import forms
from django.utils.translation import ugettext as _, ugettext_noop, ugettext_lazy

from crispy_forms.layout import Submit
from crispy_forms import layout as crispy

from corehq.apps.hqwebapp import crispy as hqcrispy
from corehq.apps.integration.models import SimprintsIntegration


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
