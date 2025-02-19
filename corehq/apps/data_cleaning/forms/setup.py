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
        self.domain = domain
        super().__init__(*args, **kwargs)
        self.fields['case_type'].choices = [(None, None)] + [
            (c, c) for c in sorted(get_case_types_for_domain(self.domain))
        ]
        self.helper = hqcrispy.HQFormHelper()
        self.helper.form_tag = False
        self.helper.layout = crispy.Layout(
            crispy.Field(
                'case_type',
                css_class="d-none",
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
        return case_type
