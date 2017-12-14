from custom.icds_reports.models import AggAwcMonthly, ChildHealthMonthlyView, CcsRecordMonthly
from django.db.models.aggregates import Sum
from django.db.models import Case, When, Q, F, IntegerField


class ISSNIPMonthlyReport(object):
    def __init__(self, config):
        self.config = config

    def filter_by(self, config, column):
        return Case(
            When(Q(**config), then=F(column)),
            default=0,
            output_field=IntegerField()
        )

    def agg_awc_monthly_data(self):
        return AggAwcMonthly.objects.filter(
            awc_id=self.config['awc_id'],
            aggregation_level=5,
            month=self.config['month']
        ).values(
            'block_name', 'awc_name', 'awc_site_code', 'infra_type_of_building', 'infra_clean_water',
            'cases_ccs_pregnant_all', 'cases_ccs_lactating_all', 'awc_days_open', 'awc_days_pse_conducted',
            'usage_num_home_visit', 'ls_awc_present',
        )

    def child_health_monthly_data(self):
        return ChildHealthMonthlyView.objects.filter(
            awc_id=self.config['awc_id'],
            month=self.config['month']
        ).values('awc_id').annotate(
            infants_0_6=Sum(self.filter_by({'age_tranche__in': [0, 6]}, 'valid_in_month')),
            children_6_36=Sum(self.filter_by({'age_tranche__in': [12, 24, 36]}, 'valid_in_month')),
            childen_36_72=Sum(self.filter_by({'age_tranche__in': [48, 60, 72]}, 'valid_in_month')),
            normal_children_breakfast=Sum(
                self.filter_by({
                    'nutrition_status_last_recorded': 'normal',
                    'age_in_months__range': [36, 72]
                }, 'doc_id')
            ),
            normal_children_hcm=Sum(
                self.filter_by({
                    'nutrition_status_last_recorded': 'normal',
                    'age_in_months__range': [36, 72]
                }, 'doc_id')
            ),
            normal_children_thr=Sum(
                self.filter_by({
                    'nutrition_status_last_recorded': 'normal',
                    'thr_eligible': 'normal'
                }, 'doc_id')
            ),
            severely_underweight_children_breakfast=Sum(
                self.filter_by({
                    'nutrition_status_last_recorded': 'severely_underweight',
                    'age_in_months__range': [36, 72]
                }, 'doc_id')
            ),
            severely_underweight_children_hcm=Sum(
                self.filter_by({
                    'nutrition_status_last_recorded': 'severely_underweight',
                    'age_in_months__range': [36, 72]
                }, 'doc_id')
            ),
            severely_underweight_children_thr=Sum(
                self.filter_by({
                    'nutrition_status_last_recorded': 'severely_underweight',
                    'thr_eligible': 'normal'
                }, 'doc_id')
            ),
        )

    def css_record_monthly(self):
        return CcsRecordMonthly.objects.filter(
            awc_id=self.config['awc_id'],
            month=self.config['month']
        ).values(
            'awc_id'
        ).annotate(
            pregnant_women_thr=Sum('pregnant') + Sum('thr_eligible'),
            lactating_women_thr=Sum('lactating') + Sum('thr_eligible'),
        )
