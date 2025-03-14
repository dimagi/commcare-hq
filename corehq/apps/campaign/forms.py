from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit
from django import forms

from django.utils.translation import gettext_lazy as _

from corehq.apps.app_manager.const import USERCASE_TYPE
from corehq.apps.campaign.models import DashboardMap, DashboardTab, DashboardReport
from corehq.apps.commtrack.const import USER_LOCATION_OWNER_MAP_TYPE
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
    )
    dashboard_tab = forms.ChoiceField(
        label=_('Dashboard Tab'),
        choices= DashboardTab.choices
    )
    # TODO Validation on display order
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
    )

    def __init__(self, *args, **kwargs):
        self.domain = kwargs.pop('domain')
        super().__init__(*args, **kwargs)

        self.fields['case_type'].choices = self._get_case_types()
        self.helper = FormHelper()
        self.helper.form_tag = False
        # TODO Check if this impacts id we do not use strcit button
        self.helper.add_input(Submit(_('submit'), 'Submit', css_class='btn btn-primary'))

    def _get_case_types(self):
        case_types = sorted(get_case_types_for_domain(self.domain))
        return [
            (case, case) for case in case_types
            if case not in (USERCASE_TYPE, USER_LOCATION_OWNER_MAP_TYPE)
        ]


class DashboardReportForm(DashboardWidgetBaseForm):

    class Meta(DashboardWidgetBaseForm.Meta):
        model = DashboardReport
        fields = DashboardWidgetBaseForm.Meta.fields + [
            'report_configuration_id',
        ]

    # TODO Maybe use choice field here
    # TODO Add validation to see if field exists
    report_configuration_id = forms.CharField(
        label=_('Report Configuration Id'),
    )

    def __init__(self, *args, **kwargs):
        self.domain = kwargs.pop('domain')
        super().__init__(*args, **kwargs)

        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.add_input(Submit(_('submit'), 'Submit', css_class='btn btn-primary'))


class WidgetChoice:
    MAP = 'map'
    REPORT = 'report'

    FORM_CLASS = {
        MAP: DashboardMapForm,  # Replace with actual form class
        REPORT: DashboardReportForm,  # Replace with actual form class
    }

    @classmethod
    def choices(cls):
        return [
            (cls.MAP, _('Map')),
            (cls.REPORT, _('Report')),
        ]
