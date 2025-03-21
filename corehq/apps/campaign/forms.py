from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit
from django import forms
from django.utils.translation import gettext_lazy as _

from corehq.apps.campaign.models import DashboardTab, DashboardMap, DashboardReport
from corehq.apps.reports.analytics.esaccessors import get_case_types_for_domain
from corehq.apps.userreports.models import ReportConfiguration


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

    def __init__(self, domain, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.domain = domain

        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.add_input(Submit(_('submit'), 'Submit', css_class='btn btn-primary'))


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
        super().__init__(domain, *args, **kwargs)
        self.fields['case_type'].choices = self._get_case_types()

    def _get_case_types(self):
        case_types = sorted(get_case_types_for_domain(self.domain))
        return [(case_type, case_type) for case_type in case_types]


class DashboardReportForm(DashboardWidgetBaseForm):

    class Meta(DashboardWidgetBaseForm.Meta):
        model = DashboardReport
        fields = DashboardWidgetBaseForm.Meta.fields + [
            'report_configuration_id',
        ]

    report_configuration_id = forms.ChoiceField(
        label=_('Report'),
    )

    def __init__(self, domain, *args, **kwargs):
        super().__init__(domain, *args, **kwargs)
        self.fields['report_configuration_id'].choices = self._get_report_configurations()

    def _get_report_configurations(self):
        report_configs = ReportConfiguration.by_domain(self.domain)
        return [
            (report.get_id, report.title)
            for report in report_configs
        ]
