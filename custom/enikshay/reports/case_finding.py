# coding=utf-8

from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn
from custom.enikshay.reports.consts import AGE_RANGES
from custom.enikshay.reports.generic import EnikshayReport, EnikshayMultiReport
from custom.enikshay.reports.sqldata.case_finding_sql_data import CaseFindingSqlData
from custom.enikshay.reports.treatment_outcome import AllTBPatientsReport


def get_for_all_ranges(slug, data):
    row = []
    for lower_bound, upper_bound in AGE_RANGES[:-1]:
        row.append(data.get('%s_age_%d_%d' % (slug, lower_bound, upper_bound), 0))

    row.append(data.get('%s_age_%d' % (slug, AGE_RANGES[-1][0]), 0))
    row.append(data.get('%s_total' % slug, 0))
    return row


class CaseFindingAllTBPatientsReport(AllTBPatientsReport):
    report_title = 'Block 1: All TB patients registered in the quarter'

    @property
    def rows(self):
        return super(CaseFindingAllTBPatientsReport, self).rows[1:4]


class AllNewAndRecurrentTBCases(EnikshayReport):
    name = 'Block 2: All new and recurrent TB cases only: from column above'
    slug = 'all_new_and_recurrent_tb_cases'

    @property
    def headers(self):
        return DataTablesHeader(
            DataTablesColumn('Age'),
            DataTablesColumn('0-4'),
            DataTablesColumn('5-14'),
            DataTablesColumn('15-24'),
            DataTablesColumn('25-34'),
            DataTablesColumn('35-44'),
            DataTablesColumn('45-54'),
            DataTablesColumn('55-64'),
            DataTablesColumn(u'≥65'),
            DataTablesColumn('total')
        )

    @property
    def model(self):
        return CaseFindingSqlData(config=self.report_config)

    @property
    def rows(self):
        model = self.model
        data = model.get_data()[0]
        return [
            ['Male'] + get_for_all_ranges('male', data),
            ['Female'] + get_for_all_ranges('female', data),
            ['Transgender'] + get_for_all_ranges('transgender', data),
            ['Total'] + get_for_all_ranges('all', data)
        ]


class LaboratoryDiagnosticActivity(EnikshayReport):
    name = 'Block 3: Laboratory diagnostic activity'
    slug = 'laboratory_diagnostic_activity'

    @property
    def headers(self):
        return DataTablesHeader(
            DataTablesColumn('Patients with presumptive TB undergoing bacteriological examination (a)'),
            DataTablesColumn('Of (a) Patients with bacteriological positive result (b)'),
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
    name = 'Block 4: TB/HIV Collaboration'
    slug = 'tb_hiv_collaboration'

    @property
    def headers(self):
        return DataTablesHeader(
            DataTablesColumn('Of all Registered TB cases,'
                             ' Number known to be tested for HIV before or during the TB treatment (a)'),
            DataTablesColumn('Of (a) Number known to be HIV infected (b)'),
            DataTablesColumn('Of (b) HIV reactive TB patients put on CPT'),
            DataTablesColumn('Of © HIV reactive TB patients put on ART (d)'),
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

    name = 'Case Finding'
    slug = 'case_finding'

    @property
    def reports(self):
        return [
            CaseFindingAllTBPatientsReport,
            AllNewAndRecurrentTBCases,
            LaboratoryDiagnosticActivity,
            TBHIVCollaboration
        ]
