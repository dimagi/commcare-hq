from __future__ import absolute_import, print_function

from __future__ import unicode_literals


from django.core.management.base import BaseCommand
from django.db import connection

PERSON_TABLE_ID = 'static-person_cases_v2'
AWC_LOCATION_TABLE_ID = 'static-awc_location'


class Command(BaseCommand):


    def handle(self,*args, **options):
        indicator_list = self.get_indicator_list()

        for indicator in indicator_list:
            indicator_result = self.execute_query(indicator)

            for ind in indicator_result:
                print("{}, {}, {}, {}".format(ind[0], indicator['num'], ind[1], ind[2]))

    def execute_query(self, params):
        query = 'select month,({0}) as numerator, {1} as denomerator from {2} where  aggregation_level=1   group by month having ({0})>{1};'
        query_with_param = query.format(*(params['num'], params['denom'], params['table']))
        print(query_with_param)
        with connection.cursor() as cursor:


            cursor.execute(query_with_param)
            return cursor.fetchall()

    def get_indicator_list(self):
        indicator_list = list()
        indicator_list.append({'num': 'sum(num_launched_awcs)', 'denom': 'sum(num_awcs)', 'table':'agg_awc'})
        indicator_list.append({'num': 'sum(cases_person_has_aadhaar)', 'denom': 'sum(cases_person_beneficiary)', 'table':'agg_awc'})
        indicator_list.append({'num': 'sum(cases_child_health)', 'denom': 'sum(cases_child_health_all)', 'table':'agg_awc'})
        indicator_list.append({'num': 'sum(cases_ccs_pregnant)', 'denom': 'sum(cases_ccs_pregnant_all)', 'table':'agg_awc'})
        indicator_list.append({'num': 'sum(cases_ccs_lactating)', 'denom': 'sum(cases_ccs_lactating_all)', 'table':'agg_awc'})
        indicator_list.append(
            {'num': 'sum(infra_clean_water)', 'denom': 'sum(num_awc_infra_last_update)', 'table': 'agg_awc'})
        indicator_list.append(
            {'num': 'sum(infra_functional_toilet)', 'denom': 'sum(num_awc_infra_last_update)', 'table': 'agg_awc'})
        indicator_list.append(
            {'num': 'sum(infra_medicine_kits)', 'denom': 'sum(num_awc_infra_last_update)', 'table': 'agg_awc'})
        indicator_list.append(
            {'num': 'sum(infra_infant_weighing_scale)', 'denom': 'sum(num_awc_infra_last_update)', 'table': 'agg_awc'})
        indicator_list.append(
            {'num': 'sum(infra_adult_weighing_scale)', 'denom': 'sum(num_awc_infra_last_update)', 'table': 'agg_awc'})



        indicator_list.append({'num': 'sum(institutional_delivery_in_month)', 'denom': 'sum(delivered_in_month)', 'table':'agg_ccs_record'})
        indicator_list.append({'num': 'sum(anc1_received_at_delivery)', 'denom': 'sum(delivered_in_month)', 'table':'agg_ccs_record'})
        indicator_list.append(
            {'num': 'sum(anc2_received_at_delivery)', 'denom': 'sum(delivered_in_month)', 'table': 'agg_ccs_record'})
        indicator_list.append(
            {'num': 'sum(anc3_received_at_delivery)', 'denom': 'sum(delivered_in_month)', 'table': 'agg_ccs_record'})
        indicator_list.append(
            {'num': 'sum(anc4_received_at_delivery)', 'denom': 'sum(delivered_in_month)', 'table': 'agg_ccs_record'})
        indicator_list.append(
            {'num': '(sum(anemic_moderate) + sum(anemic_severe))', 'denom': 'sum(pregnant)', 'table': 'agg_ccs_record'})
        indicator_list.append(
            {'num': 'sum(tetanus_complete)', 'denom': 'sum(pregnant)', 'table': 'agg_ccs_record'})
        indicator_list.append(
            {'num': 'sum(resting_during_pregnancy)', 'denom': 'sum(pregnant)', 'table': 'agg_ccs_record'})
        indicator_list.append(
            {'num': 'sum(extra_meal)', 'denom': 'sum(pregnant)', 'table': 'agg_ccs_record'})
        indicator_list.append(
            {'num': 'sum(counsel_immediate_bf)', 'denom': 'sum(trimester_3)', 'table': 'agg_ccs_record'})



        indicator_list.append(
            {'num': 'sum(bf_at_birth)', 'denom': 'sum(born_in_month)', 'table': 'agg_child_health'})
        indicator_list.append(
            {'num': 'sum(cf_initiation_in_month)', 'denom': 'sum(cf_initiation_eligible)', 'table': 'agg_child_health'})
        indicator_list.append(
            {'num': 'sum(ebf_in_month)', 'denom': 'sum(ebf_eligible)', 'table': 'agg_child_health'})
        indicator_list.append(
            {'num': 'sum(height_measured_in_month)', 'denom': 'sum(height_eligible)', 'table': 'agg_child_health'})
        indicator_list.append(
            {'num': 'sum(fully_immunized_on_time) + sum(fully_immunized_late)', 'denom': 'sum(fully_immunized_eligible)', 'table': 'agg_child_health'})
        indicator_list.append(
            {'num': 'sum(stunting_moderate) + sum(stunting_severe)', 'denom': 'sum(height_measured_in_month)', 'table': 'agg_child_health'})
        indicator_list.append(
            {'num': 'sum(nutrition_status_moderately_underweight) + sum(nutrition_status_severely_underweight)', 'denom': 'sum(nutrition_status_weighed)', 'table': 'agg_child_health'})
        indicator_list.append(
            {'num': 'sum(low_birth_weight_in_month)', 'denom': 'sum(weighed_and_born_in_month)', 'table': 'agg_child_health'})
        indicator_list.append(
            {'num': 'sum(wasting_moderate) + sum(wasting_severe)', 'denom': 'sum(weighed_and_height_measured_in_month)', 'table': 'agg_child_health'})
        indicator_list.append(
            {'num': 'sum(nutrition_status_weighed)', 'denom': 'sum(wer_eligible)', 'table': 'agg_child_health'})
        indicator_list.append(
            {'num': 'sum(low_birth_weight_in_month)', 'denom': 'sum(weighed_and_born_in_month)', 'table': 'agg_child_health'})

        return indicator_list