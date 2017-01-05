from corehq.apps.reports.datatables import DataTablesHeader
from corehq.apps.reports.filters.dates import DatespanFilter
from corehq.apps.reports.graph_models import PieChart, MultiBarChart, Axis
from corehq.apps.reports_core.filters import Choice
from corehq.apps.style.decorators import use_nvd3
from corehq.apps.userreports.models import StaticReportConfiguration
from corehq.apps.userreports.reports.factory import ReportFactory
from custom.enikshay.reports.filters import EnikshayLocationFilter, QuarterFilter
from custom.enikshay.reports.generic import EnikshayReport
from custom.enikshay.reports.sqldata.case_finding_sql_data import CaseFindingSqlData
from custom.enikshay.reports.sqldata.charts_sql_data import ChartsSqlData
from custom.enikshay.reports.sqldata.treatment_outcome_sql_data import TreatmentOutcomeSqlData
from dimagi.utils.decorators.memoized import memoized

from django.utils.translation import ugettext_lazy, ugettext as _


class WebDashboardReport(EnikshayReport):

    name = ugettext_lazy('Web Dashboard')
    report_title = ugettext_lazy('eNikshay Report Dashboard')
    slug = 'web_dashboard'
    use_datatables = False
    report_template_path = 'enikshay/web_dashboard.html'
    fields = (DatespanFilter, EnikshayLocationFilter)

    @use_nvd3
    def decorator_dispatcher(self, request, *args, **kwargs):
        return super(WebDashboardReport, self).decorator_dispatcher(request, *args, **kwargs)

    @property
    def headers(self):
        return DataTablesHeader()

    @property
    def rows(self):
        return []

    @property
    def report_context(self):
        report_context = super(WebDashboardReport, self).report_context
        report_context['total_patients'] = self.charts_sql_data[0].get('total_patients', {}).get('sort_key', 0)
        return report_context

    @property
    @memoized
    def case_finding_sql_data(self):
        return CaseFindingSqlData(config=self.report_config).get_data()

    @property
    @memoized
    def charts_sql_data(self):
        return ChartsSqlData(config=self.report_config).get_data()

    @property
    @memoized
    def treatment_outcome_sql_data(self):
        return TreatmentOutcomeSqlData(config=self.report_config).get_data()

    @property
    def charts(self):
        case_finding_sql_data = self.case_finding_sql_data[0]
        sputum_conversion_report = ReportFactory.from_spec(
            StaticReportConfiguration.by_id('static-%s-sputum_conversion' % self.domain), include_prefilters=True
        )

        filter_values = {'date': self.datespan}

        locations_id = [
            Choice(value=location_id, display='') for location_id in self.report_config.locations_id
            if location_id
        ]

        if locations_id:
            filter_values['village'] = locations_id

        sputum_conversion_report.set_filter_values(filter_values)
        sputum_conversion_data = sputum_conversion_report.get_data()[0]
        charts_sql_data = self.charts_sql_data[0]
        treatment_outcome_sql_data = self.treatment_outcome_sql_data[0]

        default_value = {'sort_key': 0}

        chart = PieChart(title=_('Cases by Gender'), key='gender', values=[])
        chart.data = [
            {'label': _('Male'), 'value': case_finding_sql_data.get('male_total', default_value)['sort_key']},
            {
                'label': _('Female'),
                'value': case_finding_sql_data.get('female_total', default_value)['sort_key']
            },
            {
                'label': _('Transgender'),
                'value': case_finding_sql_data.get('transgender_total', default_value)['sort_key']
            }
        ]

        chart2 = MultiBarChart(_('Cases By Type'), x_axis=Axis(''), y_axis=Axis(''))
        chart2.stacked = False
        chart2.showLegend = False

        positive_smear = case_finding_sql_data.get('new_positive_tb_pulmonary', default_value)['sort_key']
        negative_smear = case_finding_sql_data.get('new_negative_tb_pulmonary', default_value)['sort_key']
        positive_extra_pulmonary = case_finding_sql_data.get(
            'new_positive_tb_extrapulmonary', default_value
        )['sort_key']

        relapse_cases = case_finding_sql_data.get('recurrent_positive_tb', default_value)['sort_key']
        failure_cases = case_finding_sql_data.get('failure_positive_tb', default_value)['sort_key']
        lfu_cases = case_finding_sql_data.get('lfu_positive_tb', default_value)['sort_key']
        others_cases = case_finding_sql_data.get('others_positive_tb', default_value)['sort_key']

        chart2.add_dataset(
            _('New'),
            [
                {'x': 'Smear +ve', 'y': positive_smear},
                {'x': 'Smear -ve', 'y': negative_smear},
                {'x': 'EP', 'y': positive_extra_pulmonary}
            ]
        )

        chart2.add_dataset(
            _('Retreatment'), [
                {'x': 'Relapse', 'y': relapse_cases},
                {'x': 'Failure', 'y': failure_cases},
                {'x': 'Treatment After Default', 'y': lfu_cases},
                {'x': 'Others', 'y': others_cases}
            ]
        )

        chart3 = MultiBarChart('Sputum Conversion By Patient Type', Axis(''), Axis(''))
        chart3.stacked = True

        chart3.add_dataset('Positive', [
            {
                'x': _('New Sputum +ve (2 month IP)'),
                'y': sputum_conversion_data.get('new_sputum_positive_patient_2months_ip', 0)
            },
            {
                'x': _('New Sputum +ve (3 month IP)'),
                'y': sputum_conversion_data.get('new_sputum_positive_patient_3months_ip', 0)
            },
            {
                'x': _('Cat II (3 month IP)'),
                'y': sputum_conversion_data.get('positive_endofip_patients_cat2', 0)
            },
        ])

        chart3.add_dataset(_('Negative'), [
            {
                'x': _('New Sputum +ve (2 month IP)'),
                'y': sputum_conversion_data.get('new_sputum_negative_patient_2months_ip', 0)
            },
            {
                'x': _('New Sputum +ve (3 month IP)'),
                'y': sputum_conversion_data.get('new_sputum_negative_patient_3months_ip', 0)
            },
            {
                'x': _('Cat II (3 month IP)'),
                'y': sputum_conversion_data.get('negative_endofip_patients_cat2', 0)
            },
        ])

        chart3.add_dataset('NA', [
            {
                'x': _('New Sputum +ve (2 month IP)'),
                'y': sputum_conversion_data.get('new_sputum_na_patient_2months_ip', 0)
            },
            {
                'x': _('New Sputum +ve (3 month IP)'),
                'y': sputum_conversion_data.get('new_sputum_na_patient_3months_ip', 0)
            },
            {
                'x': _('Cat II (3 month IP)'),
                'y': sputum_conversion_data.get('na_endofip_patients_cat2', 0)
            },
        ])

        chart4 = PieChart(
            title=_('Total number of patients by category'), key='', values=[]
        )
        chart4.data = [
            {
                'label': _('Cat1'),
                'value': charts_sql_data.get('cat1_patients', default_value)['sort_key']
            },
            {
                'label': _('Cat2'),
                'value': charts_sql_data.get('cat2_patients', default_value)['sort_key']
            }
        ]

        chart5 = MultiBarChart('Outcome By Type', Axis(''), Axis(''))
        chart5.stacked = True

        chart5.add_dataset(_('Cured'), [
            {
                'x': _('New'),
                'y': treatment_outcome_sql_data.get('new_patients_cured', default_value)['sort_key']
            },
            {
                'x': _('Retreatment'),
                'y': treatment_outcome_sql_data.get('recurrent_patients_cured', default_value)['sort_key']
            }
        ])
        chart5.add_dataset('Treatment Complete', [
            {
                'x': _('New'),
                'y': treatment_outcome_sql_data.get('new_patients_treatment_complete', default_value)['sort_key']
            },
            {
                'x': _('Retreatment'),
                'y': treatment_outcome_sql_data.get(
                    'recurrent_patients_treatment_complete', default_value)['sort_key']
            }
        ])
        chart5.add_dataset('Died', [
            {
                'x': _('New'),
                'y': treatment_outcome_sql_data.get('new_patients_died', default_value)['sort_key']
            },
            {
                'x': _('Retreatment'),
                'y': treatment_outcome_sql_data.get('recurrent_patients_died', default_value)['sort_key']
            }
        ])
        chart5.add_dataset(_('Failure'), [
            {
                'x': _('New'),
                'y': treatment_outcome_sql_data.get('new_patients_treatment_failure', default_value)['sort_key']
            },
            {
                'x': _('Retreatment'),
                'y': treatment_outcome_sql_data.get(
                    'recurrent_patients_treatment_failure', default_value
                )['sort_key']
            }
        ])
        chart5.add_dataset(_('Loss to Follow-up'), [
            {
                'x': _('New'),
                'y': treatment_outcome_sql_data.get('new_patients_loss_to_follow_up', default_value)['sort_key']
            },
            {
                'x': _('Retreatment'),
                'y': treatment_outcome_sql_data.get(
                    'recurrent_patients_loss_to_follow_up', default_value
                )['sort_key']
            }
        ])
        chart5.add_dataset(_('Regimen Changed'), [
            {
                'x': _('New'),
                'y': treatment_outcome_sql_data.get('new_patients_regimen_changed', default_value)['sort_key']
            },
            {
                'x': _('Retreatment'),
                'y': treatment_outcome_sql_data.get(
                    'recurrent_patients_regimen_changed', default_value
                )['sort_key']
            }
        ])
        chart5.add_dataset('Not Evaluated', [
            {
                'x': _('New'),
                'y': treatment_outcome_sql_data.get('new_patients_not_evaluated', default_value)['sort_key']
            },
            {
                'x': _('Retreatment'),
                'y': treatment_outcome_sql_data.get('recurrent_patients_not_evaluated', default_value)['sort_key']
            }
        ])

        return [
            chart,
            chart2,
            chart3,
            chart4,
            chart5
        ]
