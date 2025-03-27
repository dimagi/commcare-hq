import json

from django import forms
from django.db.models import Max
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from crispy_forms import layout as crispy
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit

from corehq.apps.campaign.const import GAUGE_METRICS
from corehq.apps.campaign.models import (
    DashboardGauge,
    DashboardMap,
    DashboardReport,
    DashboardTab,
)
from corehq.apps.campaign.views import get_geo_case_properties, get_geo_case_properties_view
from corehq.apps.reports.analytics.esaccessors import get_case_types_for_domain
from corehq.apps.userreports.models import ReportConfiguration


class DashboardWidgetBaseForm(forms.ModelForm):

    class Meta:
        fields = [
            'title',
            'description',
            'dashboard_tab',
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

    def __init__(self, domain, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.domain = domain

        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.add_input(Submit(_('submit'), 'Submit', css_class='btn btn-primary'))

    def save(self, commit=True):
        if not self.instance.pk:
            self.instance.display_order = self._get_display_order()
        super().save(commit)

    def _get_display_order(self):
        # TODO Handle race conditions for concurrent requests to ensure consistent display_order value
        tab = self.cleaned_data['dashboard_tab']
        dashboard = self.instance.dashboard

        max_map_order = dashboard.maps.filter(
            dashboard_tab=tab
        ).aggregate(
            Max('display_order')
        )['display_order__max'] or 0

        max_report_order = dashboard.reports.filter(
            dashboard_tab=tab
        ).aggregate(
            Max('display_order')
        )['display_order__max'] or 0

        return max(max_map_order, max_report_order) + 1


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
        widget=forms.widgets.Select(choices=[]),
        help_text=_("The name of the case property storing the geo-location data of your cases."),
    )

    def __init__(self, domain, *args, **kwargs):
        super().__init__(domain, *args, **kwargs)
        self.fields['case_type'].choices = self._get_case_types()
        self.fields['geo_case_property'].widget.choices = self._get_geo_case_properties()

        self.helper.layout = crispy.Layout(
            crispy.Div(
                crispy.Field('title'),
                crispy.Field('description'),
                crispy.Field('dashboard_tab'),
                crispy.Field(
                    'case_type',
                    x_init='case_type = $el.value',
                    x_model='case_type',
                    hx_get=reverse(get_geo_case_properties_view, kwargs={'domain': self.domain}),
                    hx_trigger='change',
                    hx_target='#geo-case-property select',
                    hx_swap='innerHTML',
                    hx_indicator=".htmx-indicator",
                ),
                crispy.Div(
                    'geo_case_property',
                    css_id='geo-case-property',
                    x_init='geo_case_property = $el.value',
                    x_show='case_type !== ""',
                ),
                x_data=json.dumps({
                    'case_type': self.instance.case_type,
                }),
            )
        )

    def _get_case_types(self):
        case_types = sorted(get_case_types_for_domain(self.domain))
        return [(case_type, case_type) for case_type in case_types]

    def _get_geo_case_properties(self):
        return [
            (case_property, case_property)
            for case_property in get_geo_case_properties(self.domain, self.instance.case_type)
        ]


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


class DashboardGaugeForm(DashboardWidgetBaseForm):

    class Meta(DashboardWidgetBaseForm.Meta):
        model = DashboardGauge
        fields = DashboardWidgetBaseForm.Meta.fields + [
            'case_type',
            'metric',
        ]

    case_type = forms.ChoiceField(
        label=_('Case Type'),
    )

    metric = forms.ChoiceField(
        label=_('Metric'),
        choices=GAUGE_METRICS
    )

    def __init__(self, domain, *args, **kwargs):
        super().__init__(domain, *args, **kwargs)
        self.fields['case_type'].choices = self._get_case_types()

    def _get_case_types(self):
        case_types = sorted(get_case_types_for_domain(self.domain))
        return [(case_type, case_type) for case_type in case_types]
