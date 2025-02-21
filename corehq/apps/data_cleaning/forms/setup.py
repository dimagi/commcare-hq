import json

from crispy_forms import bootstrap as twbscrispy, layout as crispy
from django import forms
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
