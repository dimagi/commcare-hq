from __future__ import absolute_import

from __future__ import unicode_literals

from corehq.apps.locations.models import SQLLocation
from custom.icds_reports.models import AggAwcMonthly, ChildHealthMonthlyView, CcsRecordMonthly, \
    AggChildHealthMonthly, ChildHealthMonthly, AggCcsRecordMonthly
from django.db.models.aggregates import Sum, Count
from django.db.models import Case, When, Q, F, IntegerField
from django.utils.functional import cached_property

from custom.icds_reports.sqldata.awc_infrastructure import AWCInfrastructureUCR
from custom.icds_reports.sqldata.vhnd_form import VHNDFormUCR
from custom.icds_reports.utils import stunting_moderate_column, stunting_severe_column, wasting_moderate_column, \
    wasting_severe_column, DATA_NOT_ENTERED

AWC_LOCATION_LEVEL = 5


class ISSNIPMonthlyReport(object):
    def __init__(self, config, icds_feature_flag=False):
        self.config = config
        self.icds_feature_flag = icds_feature_flag

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
            'usage_num_home_visit', 'cases_person_referred', 'num_anc_visits', 'num_children_immunized',
            'aww_name', 'contact_phone_number'
        )
        return {row['awc_id']: row for row in data}

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
        return {row['awc_id']: row for row in data}

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
        return {row['awc_id']: row for row in data}

    @cached_property
    def infrastructure_data(self):
        data = AWCInfrastructureUCR(self.config.copy()).data or {}
        return {row['awc_id']: row for row in list(data.values())}

    @cached_property
    def vhnd_data(self):
        data = VHNDFormUCR(self.config.copy()).data or {}
        return {row['awc_id']: row for row in list(data.values())}

    @cached_property
    def child_health_monthly(self):
        data = ChildHealthMonthly.objects.filter(
            awc_id__in=self.config['awc_id'],
            month=self.config['month']
        ).values('awc_id').annotate(
            sc_boys_48_72=Count(self.filter_by({
                'caste': 'sc',
                'sex': 'M',
                'age_tranche__in': ['48', '60', '72'],
                'days_ration_given_child__gt': 21
            }, 'case_id', None)),
            sc_girls_48_72=Count(self.filter_by({
                'caste': 'sc',
                'sex': 'F',
                'age_tranche__in': ['48', '60', '72'],
                'days_ration_given_child__gt': 21
            }, 'case_id', None)),
            st_boys_48_72=Count(self.filter_by({
                'caste': 'st',
                'sex': 'M',
                'age_tranche__in': ['48', '60', '72'],
                'days_ration_given_child__gt': 21
            }, 'case_id', None)),
            st_girls_48_72=Count(self.filter_by({
                'caste': 'st',
                'sex': 'F',
                'age_tranche__in': ['48', '60', '72'],
                'days_ration_given_child__gt': 21
            }, 'case_id', None)),
            obc_boys_48_72=Count(self.filter_by({
                'caste': 'obc',
                'sex': 'M',
                'age_tranche__in': ['48', '60', '72'],
                'days_ration_given_child__gt': 21
            }, 'case_id', None)),
            obc_girls_48_72=Count(self.filter_by({
                'caste': 'obc',
                'sex': 'F',
                'age_tranche__in': ['48', '60', '72'],
                'days_ration_given_child__gt': 21
            }, 'case_id', None)),
            general_boys_48_72=Count(self.filter_by({
                'caste': 'other',
                'sex': 'M',
                'age_tranche__in': ['48', '60', '72'],
                'days_ration_given_child__gt': 21
            }, 'case_id', None)),
            general_girls_48_72=Count(self.filter_by({
                'caste': 'other',
                'sex': 'F',
                'age_tranche__in': ['48', '60', '72'],
                'days_ration_given_child__gt': 21
            }, 'case_id', None)),
            total_boys_48_72=Count(self.filter_by({
                'sex': 'M',
                'age_tranche__in': ['48', '60', '72'],
                'days_ration_given_child__gt': 21
            }, 'case_id', None)),
            total_girls_48_72=Count(self.filter_by({
                'sex': 'F',
                'age_tranche__in': ['48', '60', '72'],
                'days_ration_given_child__gt': 21
            }, 'case_id', None)),
            minority_boys_48_72_num=Count(self.filter_by({
                'sex': 'M',
                'age_tranche__in': ['48', '60', '72'],
                'days_ration_given_child__gt': 21,
                'minority': 'yes'
            }, 'case_id', None)),
            minority_girls_48_72_num=Count(self.filter_by({
                'sex': 'F',
                'age_tranche__in': ['48', '60', '72'],
                'days_ration_given_child__gt': 21,
                'minority': 'yes'
            }, 'case_id', None)),
            pre_sc_boys_48_72=Count(self.filter_by({
                'caste': 'sc',
                'sex': 'M',
                'age_tranche__in': ['48', '60', '72'],
                'pse_days_attended__gte': 21
            }, 'case_id', None)),
            pre_sc_girls_48_72=Count(self.filter_by({
                'caste': 'sc',
                'sex': 'F',
                'age_tranche__in': ['48', '60', '72'],
                'pse_days_attended__gte': 21
            }, 'case_id', None)),
            pre_st_boys_48_72=Count(self.filter_by({
                'caste': 'st',
                'sex': 'M',
                'age_tranche__in': ['48', '60', '72'],
                'pse_days_attended__gte': 21
            }, 'case_id', None)),
            pre_st_girls_48_72=Count(self.filter_by({
                'caste': 'st',
                'sex': 'F',
                'age_tranche__in': ['48', '60', '72'],
                'pse_days_attended__gte': 21
            }, 'case_id', None)),
            pre_obc_boys_48_72=Count(self.filter_by({
                'caste': 'obc',
                'sex': 'M',
                'age_tranche__in': ['48', '60', '72'],
                'pse_days_attended__gte': 21
            }, 'case_id', None)),
            pre_obc_girls_48_72=Count(self.filter_by({
                'caste': 'obc',
                'sex': 'F',
                'age_tranche__in': ['48', '60', '72'],
                'pse_days_attended__gte': 21
            }, 'case_id', None)),
            pre_general_boys_48_72=Count(self.filter_by({
                'caste': 'other',
                'sex': 'M',
                'age_tranche__in': ['48', '60', '72'],
                'pse_days_attended__gte': 21
            }, 'case_id', None)),
            pre_general_girls_48_72=Count(self.filter_by({
                'caste': 'other',
                'sex': 'F',
                'age_tranche__in': ['48', '60', '72'],
                'pse_days_attended__gte': 21
            }, 'case_id', None)),
            pre_total_boys_48_72=Count(self.filter_by({
                'sex': 'M',
                'age_tranche__in': ['48', '60', '72'],
                'pse_days_attended__gte': 21
            }, 'case_id', None)),
            pre_total_girls_48_72=Count(self.filter_by({
                'sex': 'F',
                'age_tranche__in': ['48', '60', '72'],
                'pse_days_attended__gte': 21
            }, 'case_id', None)),
            pre_minority_boys_48_72=Count(self.filter_by({
                'sex': 'M',
                'age_tranche__in': ['48', '60', '72'],
                'minority': 'yes',
                'pse_days_attended__gte': 21
            }, 'case_id', None)),
            pre_minority_girls_48_72=Count(self.filter_by({
                'sex': 'F',
                'age_tranche__in': ['48', '60', '72'],
                'minority': 'yes',
                'pse_days_attended__gte': 21
            }, 'case_id', None)),
        )
        return {row['awc_id']: row for row in data}

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
            }, stunting_moderate_column(self.icds_feature_flag))) + Sum(self.filter_by({
                'age_tranche__in': ['0', '6', '12', '24', '36'],
                'gender': 'M'
            }, stunting_severe_column(self.icds_feature_flag))),
            girls_stunted_0_3=Sum(self.filter_by({
                'age_tranche__in': ['0', '6', '12', '24', '36'],
                'gender': 'F'
            }, stunting_moderate_column(self.icds_feature_flag))) + Sum(self.filter_by({
                'age_tranche__in': ['0', '6', '12', '24', '36'],
                'gender': 'F'
            }, stunting_severe_column(self.icds_feature_flag))),
            boys_stunted_3_5=Sum(self.filter_by({
                'age_tranche__in': ['48', '60'],
                'gender': 'M'
            }, stunting_moderate_column(self.icds_feature_flag))) + Sum(self.filter_by({
                'age_tranche__in': ['48', '60'],
                'gender': 'M'
            }, stunting_severe_column(self.icds_feature_flag))),
            girls_stunted_3_5=Sum(self.filter_by({
                'age_tranche__in': ['48', '60'],
                'gender': 'F'
            }, stunting_moderate_column(self.icds_feature_flag))) + Sum(self.filter_by({
                'age_tranche__in': ['48', '60'],
                'gender': 'F'
            }, stunting_severe_column(self.icds_feature_flag))),
            boys_wasted_0_3=Sum(self.filter_by({
                'age_tranche__in': ['0', '6', '12', '24', '36'],
                'gender': 'M'
            }, wasting_moderate_column(self.icds_feature_flag))) + Sum(self.filter_by({
                'age_tranche__in': ['0', '6', '12', '24', '36'],
                'gender': 'M'
            }, wasting_severe_column(self.icds_feature_flag))),
            girls_wasted_0_3=Sum(self.filter_by({
                'age_tranche__in': ['0', '6', '12', '24', '36'],
                'gender': 'F'
            }, wasting_moderate_column(self.icds_feature_flag))) + Sum(self.filter_by({
                'age_tranche__in': ['0', '6', '12', '24', '36'],
                'gender': 'F'
            }, wasting_severe_column(self.icds_feature_flag))),
            boys_wasted_3_5=Sum(self.filter_by({
                'age_tranche__in': ['48', '60'],
                'gender': 'M'
            }, wasting_moderate_column(self.icds_feature_flag))) + Sum(self.filter_by({
                'age_tranche__in': ['48', '60'],
                'gender': 'M'
            }, wasting_severe_column(self.icds_feature_flag))),
            girls_wasted_3_5=Sum(self.filter_by({
                'age_tranche__in': ['48', '60'],
                'gender': 'F'
            }, wasting_moderate_column(self.icds_feature_flag))) + Sum(self.filter_by({
                'age_tranche__in': ['48', '60'],
                'gender': 'F'
            }, wasting_severe_column(self.icds_feature_flag))),
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
        return {row['awc_id']: row for row in data}

    @cached_property
    def agg_ccs_record_monthly(self):
        data = AggCcsRecordMonthly.objects.filter(
            awc_id__in=self.config['awc_id'],
            aggregation_level=AWC_LOCATION_LEVEL,
            month=self.config['month']
        ).values('awc_id').annotate(
            sc_pregnant=Sum(self.filter_by({
                'caste': 'sc',
                'ccs_status': 'pregnant'
            }, 'rations_21_plus_distributed')),
            st_pregnant=Sum(self.filter_by({
                'caste': 'st',
                'ccs_status': 'pregnant'
            }, 'rations_21_plus_distributed')),
            obc_pregnant=Sum(self.filter_by({
                'caste': 'obc',
                'ccs_status': 'pregnant'
            }, 'rations_21_plus_distributed')),
            general_pregnant=Sum(self.filter_by({
                'caste': 'general',
                'ccs_status': 'pregnant'
            }, 'rations_21_plus_distributed')),
            total_pregnant=Sum(self.filter_by({
                'ccs_status': 'pregnant'
            }, 'rations_21_plus_distributed')),
            sc_lactating=Sum(self.filter_by({
                'caste': 'sc',
                'ccs_status': 'lactating'
            }, 'rations_21_plus_distributed')),
            st_lactating=Sum(self.filter_by({
                'caste': 'st',
                'ccs_status': 'lactating'
            }, 'rations_21_plus_distributed')),
            obc_lactating=Sum(self.filter_by({
                'caste': 'obc',
                'ccs_status': 'lactating'
            }, 'rations_21_plus_distributed')),
            general_lactating=Sum(self.filter_by({
                'caste': 'general',
                'ccs_status': 'lactating'
            }, 'rations_21_plus_distributed')),
            total_lactating=Sum(self.filter_by({
                'ccs_status': 'lactating'
            }, 'rations_21_plus_distributed')),
            minority_pregnant=Sum(self.filter_by({
                'ccs_status': 'pregnant',
                'minority': 'yes'
            }, 'rations_21_plus_distributed')),
            minority_lactating=Sum(self.filter_by({
                'ccs_status': 'lactating',
                'minority': 'yes'
            }, 'rations_21_plus_distributed')),
        )
        return {row['awc_id']: row for row in data}

    def get_awc_name(self, awc_id):
        return SQLLocation.objects.get(location_id=awc_id).name

    @cached_property
    def to_pdf_format(self):
        for awc in self.config['awc_id']:
            yield dict(
                awc_name=self.get_awc_name(awc),
                agg_awc_monthly_data=self.agg_awc_monthly_data.get(awc, None),
                child_health_monthly_data=self.child_health_monthly_data.get(awc, None),
                css_record_monthly=self.css_record_monthly.get(awc, None),
                infrastructure_data=self.infrastructure_data.get(awc, None),
                vhnd_data=self.vhnd_data.get(awc, None),
                agg_ccs_record_monthly=self.agg_ccs_record_monthly.get(awc, None),
                agg_child_health_monthly=self.agg_child_health_monthly.get(awc, None),
                child_health_monthly=self.child_health_monthly.get(awc, None),
            )
