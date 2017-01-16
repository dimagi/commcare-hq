from corehq.apps.reports.datatables import DataTablesColumn, DataTablesColumnGroup, DataTablesHeader
from custom.enikshay.reports.generic import EnikshayReport, EnikshayMultiReport
from custom.enikshay.reports.const import TREATMENT_OUTCOMES
from custom.enikshay.reports.sqldata.treatment_outcome_sql_data import TreatmentOutcomeSqlData


from django.utils.translation import ugettext_lazy, ugettext as _


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

    name = ugettext_lazy('BLOCK - A: All TB patients registered in the quarter')
    slug = 'all_tb_patients'

    @property
    def headers(self):
        return NoSortDataTablesHeader(
            DataTablesColumn('Type of Patient'),
            DataTablesColumnGroup(
                _('Cured'), DataTablesColumn('1')
            ),
            DataTablesColumnGroup(
                _('Treatment Completed'), DataTablesColumn('2')
            ),
            DataTablesColumnGroup(
                _('Died'), DataTablesColumn('3')
            ),
            DataTablesColumnGroup(
                _('Treatment Failure'), DataTablesColumn('4')
            ),
            DataTablesColumnGroup(
                _('Lost to follow up'), DataTablesColumn('5')
            ),
            DataTablesColumnGroup(
                _('Regimen changed'), DataTablesColumn('6')
            ),
            DataTablesColumnGroup(
                _('Not evaluated'), DataTablesColumn('7')
            ),
            DataTablesColumnGroup(
                _('Total'), DataTablesColumn('')
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
            generate_for_all_outcomes(_('NEW CASES (Total)'), 'new_patients', data),
            generate_for_all_outcomes(
                _('Pulmonary, Microbiologically confirmed'), 'new_patients_pulmonary_microbiological',
                data
            ),
            generate_for_all_outcomes(
                _('Pulmonary, Clinically diagnosed'), 'new_patients_pulmonary_clinical',
                data
            ),
            generate_for_all_outcomes(
                _('Extra-pulmonary'), 'new_patients_extra_pulmonary',
                data
            ),
            generate_for_all_outcomes(
                _('PREVIOUSLY TREATED CASES (Total)'), 'previously_treated_patients',
                data
            ),
            generate_for_all_outcomes(
                _('Recurrent'), 'recurrent_patients',
                data
            ),
            generate_for_all_outcomes(
                _('After Treatment failure'), 'treatment_after_failure_patients',
                data
            ),
            generate_for_all_outcomes(
                _('Treatment after lost to follow up'), 'treatment_after_lfu_patients',
                data
            ),
            generate_for_all_outcomes(
                _('Other previously treated, Clinically diagnosed'), 'other_previously_treated_patients',
                data
            ),
            generate_for_all_outcomes(
                _('HIV - reactive all'), 'hiv_reactive_patients',
                data
            ),
            generate_for_all_outcomes(
                _('New'), 'new_hiv_reactive_patients',
                data
            ),
            generate_for_all_outcomes(
                _('Previously Treated'), 'previously_treated_hiv_reactive_patients',
                data
            )
        ]


class CPTAndARTReport(EnikshayReport):

    name = ugettext_lazy('BLOCK - B: CPT and ART')
    slug = 'treatment_outcome_report'

    @property
    def headers(self):
        return NoSortDataTablesHeader(
            DataTablesColumn(_('Total No. of TB patients known to be HIV infected')),
            DataTablesColumn(_('No. on CPT#')),
            DataTablesColumn(_('No. on ART#'))
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
                data.get('total_cpt_initiated', 0),
                data.get('total_initiated_on_art', 0)
            ]
        ]


class TreatmentOutcomeReport(EnikshayMultiReport):

    name = ugettext_lazy('Treatment Outcome')
    slug = 'treatment_outcome'
    report_template_path = 'enikshay/treatment_outcome.html'

    @property
    def reports(self):
        return [
            AllTBPatientsReport,
            CPTAndARTReport
        ]
