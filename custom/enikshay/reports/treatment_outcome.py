from corehq.apps.reports.datatables import DataTablesColumn, DataTablesColumnGroup, DataTablesHeader
from custom.enikshay.reports.generic import EnikshayReport, EnikshayMultiReport
from custom.enikshay.reports.consts import TREATMENT_OUTCOMES
from custom.enikshay.reports.sqldata.treatment_outcome_sql_data import TreatmentOutcomeSqlData


class NoSortDataTablesHeader(DataTablesHeader):
    no_sort = True


def generate_for_all_outcomes(title, slug, data):
    row = [
        title,
    ]
    for treatment_outcome in TREATMENT_OUTCOMES:
        row.append(
            data.get('%s_%s' % (slug, treatment_outcome))
        )
    row.append(
        data.get('total_%s' % slug)
    )
    return row


class AllTBPatientsReport(EnikshayReport):

    name = 'BLOCK - A: All TB patients registered in the quarter'
    slug = 'treatment_outcome_report'

    @property
    def headers(self):
        return NoSortDataTablesHeader(
            DataTablesColumn('Type of Patient'),
            DataTablesColumnGroup(
                'Cured', DataTablesColumn('1')
            ),
            DataTablesColumnGroup(
                'Treatment Completed', DataTablesColumn('2')
            ),
            DataTablesColumnGroup(
                'Died', DataTablesColumn('3')
            ),
            DataTablesColumnGroup(
                'Treatment Failure', DataTablesColumn('4')
            ),
            DataTablesColumnGroup(
                'Lost to follow up', DataTablesColumn('5')
            ),
            DataTablesColumnGroup(
                'Regimen changed', DataTablesColumn('6')
            ),
            DataTablesColumnGroup(
                'Not evaluated', DataTablesColumn('7')
            ),
            DataTablesColumnGroup(
                'Total', DataTablesColumn('')
            )
        )

    @property
    def model(self):
        return TreatmentOutcomeSqlData(config=self.report_config)

    @property
    def rows(self):
        model = self.model
        data = model.get_data()[0]
        return [
            generate_for_all_outcomes('NEW CASES (Total)', 'new_patients', data),
            generate_for_all_outcomes(
                'Pulmonary, Microbiologically confirmed', 'new_patients_pulmonary_microbiological',
                data
            ),
            generate_for_all_outcomes(
                'Pulmonary, Clinically diagnosed', 'new_patients_pulmonary_clinical',
                data
            ),
            generate_for_all_outcomes(
                'Extra-pulmonary', 'new_patients_extra_pulmonary',
                data
            ),
            generate_for_all_outcomes(
                'PREVIOUSLY TREATED CASES (Total)', 'previously_treated_patients',
                data
            ),
            generate_for_all_outcomes(
                'Recurrent', 'recurrent_patients',
                data
            ),
            generate_for_all_outcomes(
                'After Treatment failure', 'treatment_after_failure_patients',
                data
            ),
            generate_for_all_outcomes(
                'Treatment after lost to follow up', 'treatment_after_lfu_patients',
                data
            ),
            generate_for_all_outcomes(
                'HIV - reactive all', 'hiv_reactive_patients',
                data
            ),
            generate_for_all_outcomes(
                'New', 'new_hiv_reactive_patients',
                data
            ),
            generate_for_all_outcomes(
                'Previously Treated', 'previously_treated_hiv_reactive_patients',
                data
            )
        ]


class CPTAndARTReport(EnikshayReport):

    name = 'BLOCK - B: CPT and ART'
    slug = 'treatment_outcome_report'

    @property
    def headers(self):
        return NoSortDataTablesHeader(
            DataTablesColumn('Total No. of TB patients known to be HIV infected'),
            DataTablesColumn('No. on CPT#'),
            DataTablesColumn('No. on ART#')
        )

    @property
    def model(self):
        return TreatmentOutcomeSqlData(config=self.report_config)

    @property
    def rows(self):
        model = self.model
        data = model.get_data()[0]
        return [
            [
                data.get('total_hiv_cases', 0),
                0,  # TODO ask about CPT field
                data.get('total_initiated_on_art')
            ]
        ]


class TreatmentOutcomeReport(EnikshayMultiReport):

    name = 'Treatment Outcome'
    slug = 'treatment_outcome'

    @property
    def reports(self):
        return [
            AllTBPatientsReport,
            CPTAndARTReport
        ]
