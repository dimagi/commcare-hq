from django import forms
from corehq.apps.indicators.admin.forms import BaseDynamicIndicatorForm, CouchIndicatorForm
from mvp.models import MVPDaysSinceLastTransmission, MVPActiveCasesIndicatorDefinition, MVPChildCasesByAgeIndicatorDefinition


class MVPDaysSinceLastTransmissionForm(BaseDynamicIndicatorForm):
    doc_class = MVPDaysSinceLastTransmission


class MVPActiveCasesForm(CouchIndicatorForm):
    case_type = forms.CharField(label="Case Type")

    doc_class = MVPActiveCasesIndicatorDefinition

    def clean_case_type(self):
        if 'case_type' in self.cleaned_data:
            return self.cleaned_data['case_type'].strip()


class MVPChildCasesByAgeForm(MVPActiveCasesForm):
    max_age_in_days = forms.IntegerField(label="Max Age (Days)", required=False)
    min_age_in_days = forms.IntegerField(label="Min Age (Days)", required=False)
    show_active_only = forms.BooleanField(label="Show Active Only", initial=True, required=False)
    is_dob_in_datespan = forms.BooleanField(label="DoB falls inside Datespan", required=False)

    doc_class = MVPChildCasesByAgeIndicatorDefinition

    def __init__(self, *args, **kwargs):
        super(MVPChildCasesByAgeForm, self).__init__(*args, **kwargs)
        self.fields['case_type'].required = False
        self.fields['case_type'].help_text = "defaults to child if left blank"
