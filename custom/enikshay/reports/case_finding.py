# coding=utf-8

from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn
from custom.enikshay.reports.const import AGE_RANGES, PATIENT_TYPES
from custom.enikshay.reports.generic import EnikshayReport, EnikshayMultiReport
from custom.enikshay.reports.sqldata.case_finding_sql_data import CaseFindingSqlData

from django.utils.translation import ugettext_lazy, ugettext as _


def get_for_all_patient_types(slug, data):
    row = []
    for patient_type in PATIENT_TYPES:
        row.append(data.get('%s_%s' % (slug, patient_type), 0))
    row.append(data.get('%s_total' % slug, 0))
    return row


def get_for_all_ranges(slug, data):
    row = []
    for lower_bound, upper_bound in AGE_RANGES[:-1]:
        row.append(data.get('%s_age_%d_%d' % (slug, lower_bound, upper_bound), 0))

    row.append(data.get('%s_age_%d' % (slug, AGE_RANGES[-1][0]), 0))
    row.append(data.get('%s_total' % slug, 0))
    return row


def get_headers():
    headers = [DataTablesColumn(_('Age'))]
    for age_range in AGE_RANGES:
        if len(age_range) > 1:
            headers.append(DataTablesColumn('%d-%d' % (age_range[0], age_range[1])))
        else:
            headers.append(DataTablesColumn(u'≥%d' % age_range[0]))
    headers.append(DataTablesColumn(_('Total')))
    return headers


class CaseFindingAllTBPatientsReport(EnikshayReport):
    name = ugettext_lazy('Block 1: All TB patients notified in the date range')
    slug = 'case_finding_all_tb_patients_report'

    @property
    def model(self):
        return CaseFindingSqlData(config=self.report_config)

    @property
    def headers(self):
        return DataTablesHeader(
            DataTablesColumn(''),
            DataTablesColumn(_('New')),
            DataTablesColumn(_('Recurrent')),
            DataTablesColumn(_('Transfer-in')),
            DataTablesColumn(_('After Treatment Failure')),
            DataTablesColumn(_('Treatment After Lost to follow up')),
            DataTablesColumn(_('Other previously treated')),
            DataTablesColumn(_('Total')),
        )

    @property
    def rows(self):
        model = self.model
        data = model.get_data()[0]
        return [
            ([_('Pulmonary, microbiologically confirmed')] +
             get_for_all_patient_types('pulmonary_microbiologically', data)),
            [_('Pulmonary, clinically diagnosed')] + get_for_all_patient_types('pulmonary_clinical', data),
            [_('Extra pulmonary')] + get_for_all_patient_types('extra_pulmonary', data),
            [_('Total')] + get_for_all_patient_types('total', data),
        ]


class AllNewAndRecurrentTBCases(EnikshayReport):
    name = ugettext_lazy('Block 2: All new and recurrent TB cases only: from column above')
    slug = 'all_new_and_recurrent_tb_cases'

    @property
    def headers(self):
        return DataTablesHeader(
            *get_headers()
        )

    @property
    def model(self):
        return CaseFindingSqlData(config=self.report_config)

    @property
    def rows(self):
        model = self.model
        data = model.get_data()[0]
        return [
            [_('Male')] + get_for_all_ranges('male', data),
            [_('Female')] + get_for_all_ranges('female', data),
            [_('Transgender')] + get_for_all_ranges('transgender', data),
            [_('Total')] + get_for_all_ranges('all', data)
        ]


class LaboratoryDiagnosticActivity(EnikshayReport):
    name = ugettext_lazy('Block 3: Laboratory diagnostic activity')
    slug = 'laboratory_diagnostic_activity'

    @property
    def headers(self):
        return DataTablesHeader(
            DataTablesColumn(_('Patients with presumptive TB undergoing bacteriological examination (a)')),
            DataTablesColumn(_('Of (a) Patients with bacteriological positive result (b)')),
        )

    @property
    def model(self):
        return CaseFindingSqlData(config=self.report_config)

    @property
    def rows(self):
        model = self.model
        data = model.get_data()[0]
        return [
            [data.get('patients_with_presumptive_tb', 0), data.get('patients_with_positive_tb', 0)]
        ]


class TBHIVCollaboration(EnikshayReport):
    name = ugettext_lazy('Block 4: TB/HIV Collaboration')
    slug = 'tb_hiv_collaboration'

    @property
    def headers(self):
        return DataTablesHeader(
            DataTablesColumn(_('Of all Notified TB cases, '
                               'Number known to be tested for HIV before or during the TB treatment (a)')),
            DataTablesColumn(_('Of (a) Number known to be HIV infected (b)')),
            DataTablesColumn(_('Of (b) HIV reactive TB patients put on CPT')),
            DataTablesColumn(_('Of (c) HIV reactive TB patients put on ART (d)')),
        )

    @property
    def model(self):
        return CaseFindingSqlData(config=self.report_config)

    @property
    def rows(self):
        model = self.model
        data = model.get_data()[0]
        return [
            [
                data.get('all_hiv_tested', 0),
                data.get('hiv_reactive', 0),
                data.get('hiv_reactive_cpt', 0),
                data.get('hiv_reactive_art', 0)
            ]
        ]


class CaseFindingReport(EnikshayMultiReport):

    name = ugettext_lazy('Case Finding')
    slug = 'case_finding'

    @property
    def reports(self):
        return [
            CaseFindingAllTBPatientsReport,
            AllNewAndRecurrentTBCases,
            LaboratoryDiagnosticActivity,
            TBHIVCollaboration
        ]
