from __future__ import absolute_import

from __future__ import unicode_literals

from corehq.apps.locations.models import SQLLocation
from custom.icds_reports.models import AggAwcMonthly, ChildHealthMonthlyView, CcsRecordMonthly, \
    AggChildHealthMonthly
from django.db.models.aggregates import Sum, Count
from django.db.models import Case, When, Q, F, IntegerField
from django.utils.functional import cached_property

from custom.icds_reports.sqldata import AWCInfrastructureUCR, VHNDFormUCR, CcsRecordMonthlyURC, \
    ChildHealthMonthlyURC

DATA_NOT_ENTERED = "Data Not Entered"
AWC_LOCATION_LEVEL = 5


class ISSNIPMonthlyReport(object):
    def __init__(self, config):
        self.config = config

    def filter_by(self, config, column, default=0):
        return Case(
            When(Q(**config), then=F(column)),
            default=default,
            output_field=IntegerField()
        )

    @cached_property
    def agg_awc_monthly_data(self):
        data = AggAwcMonthly.objects.filter(
            awc_id__in=self.config['awc_id'],
            aggregation_level=AWC_LOCATION_LEVEL,
            month=self.config['month']
        ).values(
            'block_name', 'awc_id', 'awc_name', 'awc_site_code', 'infra_type_of_building', 'infra_clean_water',
            'cases_ccs_pregnant_all', 'cases_ccs_lactating_all', 'awc_days_open', 'awc_days_pse_conducted',
            'usage_num_home_visit', 'cases_person_referred', 'num_anc_visits', 'num_children_immunized', 'aww_name',
            'contact_phone_number'
        )
        return data

    @cached_property
    def child_health_monthly_data(self):
        data = ChildHealthMonthlyView.objects.filter(
            awc_id__in=self.config['awc_id'],
            month=self.config['month']
        ).values('awc_id').annotate(
            infants_0_6=Sum(self.filter_by({'age_in_months__range': [0, 6]}, 'valid_in_month')),
            children_6_36=Sum(self.filter_by({'age_in_months__range': [7, 36]}, 'valid_in_month')),
            children_36_72=Sum(self.filter_by({'age_in_months__range': [37, 72]}, 'valid_in_month')),
            normal_children_breakfast_and_hcm=Count(
                self.filter_by({
                    'nutrition_status_last_recorded': 'normal',
                    'age_in_months__range': [36, 72]
                }, 'case_id', None)
            ),
            normal_children_thr=Sum(
                self.filter_by({
                    'nutrition_status_last_recorded': 'normal',
                }, 'thr_eligible')
            ),
            severely_underweight_children_breakfast_and_hcm=Count(
                self.filter_by({
                    'nutrition_status_last_recorded': 'severely_underweight',
                    'age_in_months__range': [36, 72]
                }, 'case_id', None)
            ),
            severely_underweight_children_thr=Sum(
                self.filter_by({
                    'nutrition_status_last_recorded': 'severely_underweight',
                }, 'thr_eligible')
            ),
        )
        return data

    @cached_property
    def css_record_monthly(self):
        data = CcsRecordMonthly.objects.filter(
            awc_id__in=self.config['awc_id'],
            month=self.config['month']
        ).values(
            'awc_id'
        ).annotate(
            pregnant_women_thr=Sum(
                self.filter_by({
                    'pregnant__gt': 0,
                    'thr_eligible__gt': 0
                }, 'pregnant')
            ),
            lactating_women_thr=Sum(
                self.filter_by({
                    'lactating__gt': 0,
                    'thr_eligible__gt': 0
                }, 'lactating')
            )
        )
        return data

    @cached_property
    def infrastructure_data(self):
        data = AWCInfrastructureUCR(self.config.copy()).data
        return list(data.values()) if data else []

    @cached_property
    def vhnd_data(self):
        data = VHNDFormUCR(self.config.copy()).data
        return list(data.values()) if data else []

    @cached_property
    def ccs_record_monthly_ucr(self):
        data = CcsRecordMonthlyURC(self.config.copy()).data
        return data

    @cached_property
    def child_health_monthly_ucr(self):
        data = ChildHealthMonthlyURC(self.config.copy()).data
        return data

    @cached_property
    def agg_child_health_monthly(self):
        data = AggChildHealthMonthly.objects.filter(
            awc_id__in=self.config['awc_id'],
            aggregation_level=AWC_LOCATION_LEVEL,
            month=self.config['month']
        ).values('awc_id').annotate(
            boys_normal_0_3=Sum(self.filter_by({
                'age_tranche__in': ['0', '6', '12', '24', '36'],
                'gender': 'M'
            }, 'nutrition_status_normal')),
            girls_normal_0_3=Sum(self.filter_by({
                'age_tranche__in': ['0', '6', '12', '24', '36'],
                'gender': 'F'
            }, 'nutrition_status_normal')),
            boys_normal_3_5=Sum(self.filter_by({
                'age_tranche__in': ['48', '60'],
                'gender': 'M'
            }, 'nutrition_status_normal')),
            girls_normal_3_5=Sum(self.filter_by({
                'age_tranche__in': ['48', '60'],
                'gender': 'F'
            }, 'nutrition_status_normal')),
            boys_moderately_0_3=Sum(self.filter_by({
                'age_tranche__in': ['0', '6', '12', '24', '36'],
                'gender': 'M'
            }, 'nutrition_status_moderately_underweight')),
            girls_moderately_0_3=Sum(self.filter_by({
                'age_tranche__in': ['0', '6', '12', '24', '36'],
                'gender': 'F'
            }, 'nutrition_status_moderately_underweight')),
            boys_moderately_3_5=Sum(self.filter_by({
                'age_tranche__in': ['48', '60'],
                'gender': 'M'
            }, 'nutrition_status_moderately_underweight')),
            girls_moderately_3_5=Sum(self.filter_by({
                'age_tranche__in': ['48', '60'],
                'gender': 'F'
            }, 'nutrition_status_moderately_underweight')),
            boys_severely_0_3=Sum(self.filter_by({
                'age_tranche__in': ['0', '6', '12', '24', '36'],
                'gender': 'M'
            }, 'nutrition_status_severely_underweight')),
            girls_severely_0_3=Sum(self.filter_by({
                'age_tranche__in': ['0', '6', '12', '24', '36'],
                'gender': 'F'
            }, 'nutrition_status_severely_underweight')),
            boys_severely_3_5=Sum(self.filter_by({
                'age_tranche__in': ['48', '60'],
                'gender': 'M'
            }, 'nutrition_status_severely_underweight')),
            girls_severely_3_5=Sum(self.filter_by({
                'age_tranche__in': ['48', '60'],
                'gender': 'F'
            }, 'nutrition_status_severely_underweight')),
            boys_stunted_0_3=Sum(self.filter_by({
                'age_tranche__in': ['0', '6', '12', '24', '36'],
                'gender': 'M'
            }, 'stunting_moderate')) + Sum(self.filter_by({
                'age_tranche__in': ['0', '6', '12', '24', '36'],
                'gender': 'M'
            }, 'stunting_severe')),
            girls_stunted_0_3=Sum(self.filter_by({
                'age_tranche__in': ['0', '6', '12', '24', '36'],
                'gender': 'F'
            }, 'stunting_moderate')) + Sum(self.filter_by({
                'age_tranche__in': ['0', '6', '12', '24', '36'],
                'gender': 'F'
            }, 'stunting_severe')),
            boys_stunted_3_5=Sum(self.filter_by({
                'age_tranche__in': ['48', '60'],
                'gender': 'M'
            }, 'stunting_moderate')) + Sum(self.filter_by({
                'age_tranche__in': ['48', '60'],
                'gender': 'M'
            }, 'stunting_severe')),
            girls_stunted_3_5=Sum(self.filter_by({
                'age_tranche__in': ['48', '60'],
                'gender': 'F'
            }, 'stunting_moderate')) + Sum(self.filter_by({
                'age_tranche__in': ['48', '60'],
                'gender': 'F'
            }, 'stunting_severe')),
            boys_wasted_0_3=Sum(self.filter_by({
                'age_tranche__in': ['0', '6', '12', '24', '36'],
                'gender': 'M'
            }, 'wasting_moderate')) + Sum(self.filter_by({
                'age_tranche__in': ['0', '6', '12', '24', '36'],
                'gender': 'M'
            }, 'wasting_severe')),
            girls_wasted_0_3=Sum(self.filter_by({
                'age_tranche__in': ['0', '6', '12', '24', '36'],
                'gender': 'F'
            }, 'wasting_moderate')) + Sum(self.filter_by({
                'age_tranche__in': ['0', '6', '12', '24', '36'],
                'gender': 'F'
            }, 'wasting_severe')),
            boys_wasted_3_5=Sum(self.filter_by({
                'age_tranche__in': ['48', '60'],
                'gender': 'M'
            }, 'wasting_moderate')) + Sum(self.filter_by({
                'age_tranche__in': ['48', '60'],
                'gender': 'M'
            }, 'wasting_severe')),
            girls_wasted_3_5=Sum(self.filter_by({
                'age_tranche__in': ['48', '60'],
                'gender': 'F'
            }, 'wasting_moderate')) + Sum(self.filter_by({
                'age_tranche__in': ['48', '60'],
                'gender': 'F'
            }, 'wasting_severe')),
            sc_boys_6_36=Sum(self.filter_by({
                'caste': 'sc',
                'gender': 'M',
                'age_tranche__in': ['6', '12', '24', '36']
            }, 'rations_21_plus_distributed')),
            sc_girls_6_36=Sum(self.filter_by({
                'caste': 'sc',
                'gender': 'F',
                'age_tranche__in': ['6', '12', '24', '36']
            }, 'rations_21_plus_distributed')),
            st_boys_6_36=Sum(self.filter_by({
                'caste': 'st',
                'gender': 'M',
                'age_tranche__in': ['6', '12', '24', '36']
            }, 'rations_21_plus_distributed')),
            st_girls_6_36=Sum(self.filter_by({
                'caste': 'st',
                'gender': 'F',
                'age_tranche__in': ['6', '12', '24', '36']
            }, 'rations_21_plus_distributed')),
            obc_boys_6_36=Sum(self.filter_by({
                'caste': 'obc',
                'gender': 'M',
                'age_tranche__in': ['6', '12', '24', '36']
            }, 'rations_21_plus_distributed')),
            obc_girls_6_36=Sum(self.filter_by({
                'caste': 'obc',
                'gender': 'F',
                'age_tranche__in': ['6', '12', '24', '36']
            }, 'rations_21_plus_distributed')),
            general_boys_6_36=Sum(self.filter_by({
                'caste': 'other',
                'gender': 'M',
                'age_tranche__in': ['6', '12', '24', '36']
            }, 'rations_21_plus_distributed')),
            general_girls_6_36=Sum(self.filter_by({
                'caste': 'other',
                'gender': 'F',
                'age_tranche__in': ['6', '12', '24', '36']
            }, 'rations_21_plus_distributed')),
            total_boys_6_36=Sum(self.filter_by({
                'gender': 'M',
                'age_tranche__in': ['6', '12', '24', '36']
            }, 'rations_21_plus_distributed')),
            total_girls_6_36=Sum(self.filter_by({
                'gender': 'F',
                'age_tranche__in': ['6', '12', '24', '36']
            }, 'rations_21_plus_distributed')),
            minority_boys_6_36_num=Sum(self.filter_by({
                'gender': 'M',
                'age_tranche__in': ['6', '12', '24', '36'],
                'minority': 'yes'
            }, 'rations_21_plus_distributed')),
            minority_girls_6_36_num=Sum(self.filter_by({
                'gender': 'F',
                'age_tranche__in': ['6', '12', '24', '36'],
                'minority': 'yes'
            }, 'rations_21_plus_distributed')),

        )
        return data

    def get_awc_name(self, awc_id):
        return SQLLocation.objects.get(location_id=awc_id).name,

    @cached_property
    def to_pdf_format(self):
        for awc in self.config['awc_id']:
            agg_awc_monthly_data = [x for x in self.agg_awc_monthly_data if x['awc_id'] == awc]
            child_health_monthly_data = [x for x in self.child_health_monthly_data if x['awc_id'] == awc]
            css_record_monthly = [x for x in self.css_record_monthly if x['awc_id'] == awc]
            infrastructure_data = [x for x in self.infrastructure_data if x['awc_id'] == awc]
            vhnd_data = [x for x in self.vhnd_data if x['awc_id'] == awc]
            agg_child_health_monthly = [x for x in self.agg_child_health_monthly if x['awc_id'] == awc]
            yield dict(
                awc_name=self.get_awc_name(awc),
                agg_awc_monthly_data=agg_awc_monthly_data[0] if agg_awc_monthly_data else None,
                child_health_monthly_data=child_health_monthly_data[0] if child_health_monthly_data else None,
                css_record_monthly=css_record_monthly[0] if css_record_monthly else None,
                infrastructure_data=infrastructure_data[-1] if infrastructure_data else None,
                vhnd_data=vhnd_data[-1] if vhnd_data else None,
                ccs_record_monthly_ucr=(
                    self.ccs_record_monthly_ucr[awc] if awc in self.ccs_record_monthly_ucr else None
                ),
                child_health_monthly_ucr=(
                    self.child_health_monthly_ucr[awc] if awc in self.child_health_monthly_ucr else None
                ),
                agg_child_health_monthly=agg_child_health_monthly[0] if agg_child_health_monthly else None,
            )
