from __future__ import absolute_import
from django.utils.translation import ugettext_lazy, ugettext as _

from corehq.apps.locations.permissions import location_safe
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn
from corehq.apps.reports_core.filters import Choice
from corehq.apps.userreports.models import StaticReportConfiguration
from corehq.apps.userreports.reports.factory import ReportFactory
from corehq.apps.userreports.reports.view import get_filter_values
from custom.enikshay.reports.filters import PeriodFilter, EnikshayLocationFilter
from custom.enikshay.reports.generic import EnikshayReport
from dimagi.utils.decorators.memoized import memoized


@location_safe
class AdherenceReport(EnikshayReport):
    slug = 'adherence_report'
    name = ugettext_lazy('Adherence')

    use_datatables = True
    ajax_pagination = True

    fields = (PeriodFilter, EnikshayLocationFilter)

    @property
    def headers(self):
        return DataTablesHeader(
            DataTablesColumn(_('Beneficiary ID'), sortable=False),
            DataTablesColumn(_('Beneficiary Name'), sortable=False),
            DataTablesColumn(_("Father/Husband's Name"), sortable=False),
            DataTablesColumn(_('Gender'), sortable=False),
            DataTablesColumn(_('Age'), sortable=False),
            DataTablesColumn(_('Mobile No. 1'), sortable=False),
            DataTablesColumn(_('Mobile No. 2'), sortable=False),
            DataTablesColumn(_('Address'), sortable=False),
            DataTablesColumn(_('Ward No.'), sortable=False),
            DataTablesColumn(_('Block / Taluka / Mandal'), sortable=False),
            DataTablesColumn(_('District'), sortable=False),
            DataTablesColumn(_('Village / Town / City'), sortable=False),
            DataTablesColumn(_('State'), sortable=False),
            DataTablesColumn(_('Pincode'), sortable=False),
            DataTablesColumn(_('Treating Provider Name'), sortable=False),
            DataTablesColumn(_('Treating Provider ID'), sortable=False),
            DataTablesColumn(_('Treatment Supervisor Name'), sortable=False),
            DataTablesColumn(_('TS Mobile NO.'), sortable=False),
            DataTablesColumn(_('Assigned FO'), sortable=False),
            DataTablesColumn(_('Date of Notification'), sortable=False),
            DataTablesColumn(_('Date of Rx. Start'), sortable=False),
            DataTablesColumn(_('Adherence Mechanism Assigned (Current)'), sortable=False),
            DataTablesColumn(_('Date of 99D Registration'), sortable=False),
            DataTablesColumn(_('Date of MERM Registration'), sortable=False),
            DataTablesColumn(_('% Adherence Reported'), sortable=False),
            DataTablesColumn(_('% of Adherence by 99D'), sortable=False),
            DataTablesColumn(_('% Adherence by Treatment Supervisor'), sortable=False),
            DataTablesColumn(_('% Adherence by FO'), sortable=False),
            DataTablesColumn(_('% Adherence by Patient'), sortable=False),
            DataTablesColumn(_('% Adherence by Provider'), sortable=False),
            DataTablesColumn(_('% Adherence by Other'), sortable=False),
            DataTablesColumn(_('% Adherence by MERM'), sortable=False),
            DataTablesColumn(_('% Unknown Doses'), sortable=False),
            DataTablesColumn(_('% Missed Doses'), sortable=False),
            DataTablesColumn(_('Interim Rx. Outcome'), sortable=False),
            DataTablesColumn(_('Date of last household visit'), sortable=False)
        )

    @property
    def ucr_report(self):
        spec = StaticReportConfiguration.by_id('static-%s-adherence' % self.domain)
        report = ReportFactory.from_spec(
            spec, include_prefilters=True
        )

        filter_values = get_filter_values(spec.ui_filters, self.request_params, self.request.couch_user)
        locations_id = [
            Choice(value=location_id, display='') for location_id in self.report_config.locations_id
            if location_id
        ]

        if locations_id:
            filter_values['village'] = locations_id

        report.set_filter_values(filter_values)
        return report

    @property
    def period(self):
        return self.request.GET.get('period', 'three_day')

    @property
    @memoized
    def rows(self):
        period = self.period

        data = self.ucr_report.get_data(self.pagination.start, self.pagination.count)
        rows = []
        for row in data:
            rows.append([
                row.get('person_id_property', ''),
                row.get('person_name', ''),
                row.get('husband_father_name', ''),
                row.get('sex', ''),
                row.get('age_entered', ''),
                row.get('phone_number', ''),
                row.get('secondary_phone', ''),
                row.get('current_address_first_line', ''),
                row.get('current_address_ward', ''),
                row.get('current_address_block_taluka_mandal', ''),
                row.get('current_address_district_choice', ''),
                row.get('current_address_village_town_city', ''),
                row.get('current_address_state_choice', ''),
                row.get('current_address_postal_code', ''),
                row.get('person_owner_id', ''),
                row.get('person_owner_id', ''),
                row.get('treatment_supervisor_name', ''),
                row.get('treatment_supervisor_phone', ''),
                row.get('fo', ''),
                row.get('date_of_notification', ''),
                row.get('treatment_initiation_date', ''),
                row.get('adherence_tracking_mechanism', ''),
                row.get('date_of_99d_registration', ''),
                row.get('date_of_merm_registration', ''),
                row.get('{}_adherence_score'.format(period), ''),
                row.get('{}_adherence_score_99DOTS'.format(period), ''),
                row.get('{}_adherence_score_treatment_supervisor'.format(period), ''),
                row.get('{}_adherence_score_field_officer'.format(period), ''),
                row.get('{}_adherence_score_patient'.format(period), ''),
                row.get('{}_adherence_score_provider'.format(period), ''),
                row.get('{}_adherence_score_other'.format(period), ''),
                row.get('{}_adherence_score_MERM'.format(period), ''),
                row.get('{}_unknown_score'.format(period), ''),
                row.get('{}_missed_score'.format(period), ''),
                row.get('current_interim_outcome', ''),
                row.get('visit_date', '')
            ])
        return rows

    @property
    def total_records(self):
        return int(self.ucr_report.get_total_records())

    @property
    def shared_pagination_GET_params(self):
        return [
            dict(name='period', value=self.request.GET.getlist('period')),
            dict(name='locations_id', value=self.request.GET.getlist('locations_id')),
        ]
