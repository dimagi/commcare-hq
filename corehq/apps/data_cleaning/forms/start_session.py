import json

from crispy_forms import bootstrap as twbscrispy, layout as crispy
from django import forms
from django.template.loader import render_to_string
from django.utils.translation import gettext_lazy, gettext as _

from corehq.apps.hqwebapp import crispy as hqcrispy
from corehq.apps.reports.analytics.esaccessors import get_case_types_for_domain


class SelectCaseTypeForm(forms.Form):
    case_type = forms.ChoiceField(
        label=gettext_lazy("Case Type"),
        required=False,
    )

    def __init__(self, domain, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.allowed_case_types = sorted(get_case_types_for_domain(domain))
        self.fields['case_type'].choices = [(None, None)] + [
            (c, c) for c in self.allowed_case_types
        ]
        self.helper = hqcrispy.HQFormHelper()
        self.helper.form_tag = False
        self.helper.layout = crispy.Layout(
            crispy.Field(
                'case_type',
                x_select2=json.dumps({
                    "placeholder": _("Select a Case Type"),
                }),
            ),
            hqcrispy.FormActions(
                twbscrispy.StrictButton(
                    _("Next"),
                    type="submit",
                    css_class="btn btn-primary",
                ),
                css_class="mb-0"
            ),
        )

    def clean_case_type(self):
        case_type = self.cleaned_data['case_type']
        if not self.cleaned_data['case_type']:
            raise forms.ValidationError(_("Please select a case type to continue."))
        if case_type not in self.allowed_case_types:
            raise forms.ValidationError(_("'{}' is not a valid case type").format(case_type))
        return case_type


class ResumeOrRestartCaseSessionForm(forms.Form):
    case_type = forms.CharField(
        label=gettext_lazy("Case Type"),
        required=False,
    )
    next_step = forms.ChoiceField(
        label=gettext_lazy("Next Step"),
        required=False,
        widget=forms.RadioSelect,
        choices=(
            ('resume', gettext_lazy("Resume the session.")),
            ('new', gettext_lazy("Start a new session and delete the existing session.")),
        ),
    )

    def __init__(self, domain, container_id, cancel_url, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.allowed_case_types = sorted(get_case_types_for_domain(domain))
        self.helper = hqcrispy.HQFormHelper()
        self.helper.form_tag = False
        self.helper.layout = crispy.Layout(
            crispy.HTML(render_to_string(
                'data_cleaning/forms/partials/active_session_exists.html', {}
            )),
            crispy.Field(
                'case_type',
                readonly="",
                css_class="form-control-plaintext",
            ),
            'next_step',
            hqcrispy.FormActions(
                twbscrispy.StrictButton(
                    _("Start Session"),
                    type="submit",
                    css_class="btn btn-primary",
                ),
                twbscrispy.StrictButton(
                    _("Go Back"),
                    type="button",
                    css_class="btn btn-outline-primary",
                    hx_get=cancel_url,
                    hx_target=f"#{container_id}",
                    hx_disabled_elt='this',
                ),
                css_class="mb-0"
            ),
        )

    def clean_case_type(self):
        case_type = self.cleaned_data['case_type']
        if case_type not in self.allowed_case_types:
            raise forms.ValidationError(_("'{}' is not a valid case type").format(case_type))
        return case_type
