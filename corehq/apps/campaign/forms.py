from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit
from django import forms
from django.utils.translation import gettext_lazy as _

from corehq.apps.campaign.models import DashboardTab, DashboardMap
from corehq.apps.reports.analytics.esaccessors import get_case_types_for_domain


class DashboardWidgetBaseForm(forms.ModelForm):

    class Meta:
        fields = [
            'title',
            'description',
            'dashboard_tab',
            'display_order',
        ]

    title = forms.CharField(
        label=_('Title'),
        required=True,
    )
    description = forms.CharField(
        label=_('Description'),
        required=False,
    )
    dashboard_tab = forms.ChoiceField(
        label=_('Dashboard Tab'),
        choices=DashboardTab.choices
    )
    display_order = forms.IntegerField(
        label=_('Display Order'),
    )


class DashboardMapForm(DashboardWidgetBaseForm):

    class Meta(DashboardWidgetBaseForm.Meta):
        model = DashboardMap
        fields = DashboardWidgetBaseForm.Meta.fields + [
            'case_type',
            'geo_case_property',
        ]

    case_type = forms.ChoiceField(
        label=_('Case Type'),
    )
    geo_case_property = forms.CharField(
        label=_('Geo Case Property'),
        help_text=_("The name of the case property storing the geo-location data of your cases."),
    )

    def __init__(self, domain, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.domain = domain
        self.fields['case_type'].choices = self._get_case_types()

        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.add_input(Submit(_('submit'), 'Submit', css_class='btn btn-primary'))

    def _get_case_types(self):
        case_types = sorted(get_case_types_for_domain(self.domain))
        return [(case, case) for case in case_types]
