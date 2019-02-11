from __future__ import absolute_import, print_function
from __future__ import unicode_literals

import dateutil
import six

from django.core.management.base import BaseCommand
from django.db import connections

from corehq.sql_db.connections import get_icds_ucr_db_alias


class Command(BaseCommand):

    def add_arguments(self, parser):
        parser.add_argument(
            'input_month'
        )

    def handle(self, input_month, *args, **options):
        indicator_list = self.get_indicator_list()
        indicator_ratio = []

        for indicator in indicator_list:
            input_month = six.text_type(dateutil.parser.parse(input_month).date().replace(day=1))
            query = self.prepare_query(indicator, input_month)
            ratio_check = self.execute_query(query)
            ratio_check = [(indicator["indicators"][i]['indicator'], res) for i, res in enumerate(ratio_check)]
            indicator_ratio.extend(ratio_check)

        for indicator in indicator_ratio:
            print("{0}: {1}".format(*indicator))

    def execute_query(self, query):
        db_alias = get_icds_ucr_db_alias()
        with connections[db_alias].cursor() as cursor:
            cursor.execute(query)
            return cursor.fetchall()[0]

    def prepare_query(self, indicator_dict, input_month):
        query_param = dict()
        query_param['table_name'] = indicator_dict['table']
        indicators = list()
        for indicator in indicator_dict['indicators']:
            indicators.append("({numerator})>({denominator})".format(**indicator))

        query_param['indicators'] = ','.join(indicators)
        query_param['input_month'] = input_month

        query = """
        select  {indicators} from  {table_name}  where  aggregation_level=5  and month='{input_month}'
        """.format(**query_param)

        return query

    def get_indicator_list(self):
        indicator_list = [
            {
                'table': 'agg_awc',
                'indicators': [
                    {'numerator': 'sum(num_launched_awcs)',
                     'denominator': 'sum(num_awcs)',
                     'indicator': 'AWCs launched'},
                    {'numerator': 'sum(cases_person_has_aadhaar)',
                     'denominator': 'sum(cases_person_beneficiary)',
                     'indicator': 'Adhaar-seeded beneficiaries'},
                    {'numerator': 'sum(cases_child_health)',
                     'denominator': 'sum(cases_child_health_all)',
                     'indicator': 'Percent children (0-6 years) enrolled for ICDS services'},
                    {'numerator': 'sum(cases_ccs_pregnant)',
                     'denominator': 'sum(cases_ccs_pregnant_all)',
                     'indicator': 'Percent pregnant women enrolled for ICDS services'},
                    {'numerator': 'sum(cases_ccs_lactating)',
                     'denominator': 'sum(cases_ccs_lactating_all)',
                     'indicator': 'Percent lactating women enrolled for ICDS services'},
                    {'numerator': 'sum(infra_clean_water)',
                     'denominator': 'sum(num_awc_infra_last_update)',
                     'indicator': 'AWCs Reported Clean Drinking Water'},
                    {'numerator': 'sum(infra_functional_toilet)',
                     'denominator': 'sum(num_awc_infra_last_update)',
                     'indicator': 'AWCs Reported Functional Toilet'},
                    {'numerator': 'sum(infra_medicine_kits)',
                     'denominator': 'sum(num_awc_infra_last_update)',
                     'indicator': 'AWCs Reported Medicine Kit'},
                    {'numerator': 'sum(infra_infant_weighing_scale)',
                     'denominator': 'sum(num_awc_infra_last_update)',
                     'indicator': 'AWCs Reported Weighing Scale: Infants'},
                    {'numerator': 'sum(infra_adult_weighing_scale)',
                     'denominator': 'sum(num_awc_infra_last_update)',
                     'indicator': 'AWCs Reported Weighing Scale: Mother and Child'},
                ],
            },
            {
                "table": "agg_ccs_record",
                "indicators": [
                    {'numerator': 'sum(institutional_delivery_in_month)',
                     'denominator': 'sum(delivered_in_month)',
                     'indicator': 'Institutional deliveries'},
                    {'numerator': 'sum(anc1_received_at_delivery)',
                     'denominator': 'sum(delivered_in_month)',
                     'indicator': 'Percent women had at least 1 ANC visit by delivery'},
                    {'numerator': 'sum(anc2_received_at_delivery)',
                     'denominator': 'sum(delivered_in_month)',
                     'indicator': 'Percent women had at least 2 ANC visits by delivery'},
                    {'numerator': 'sum(anc3_received_at_delivery)',
                     'denominator': 'sum(delivered_in_month)',
                     'indicator': 'Percent women had at least 3 ANC visits by delivery'},
                    {'numerator': 'sum(anc4_received_at_delivery)',
                     'denominator': 'sum(delivered_in_month)',
                     'indicator': 'Percent women had at least 4 ANC visits by delivery'},
                    {'numerator': '(sum(anemic_moderate) + sum(anemic_severe))',
                     'denominator': 'sum(pregnant)',
                     'indicator': 'Percent Anemic'},
                    {'numerator': 'sum(tetanus_complete)',
                     'denominator': 'sum(pregnant)',
                     'indicator': 'Percent tetanus complete'},
                    {'numerator': 'sum(resting_during_pregnancy)',
                     'denominator': 'sum(pregnant)',
                     'indicator': 'Percent women Resting during pregnancy'},
                    {'numerator': 'sum(extra_meal)',
                     'denominator': 'sum(pregnant)',
                     'indicator': 'Percent eating extra meal during pregnancy'},
                    {'numerator': 'sum(counsel_immediate_bf)',
                     'denominator': 'sum(trimester_3)',
                     'indicator': 'Percent trimester 3 women Counselled on immediate EBF during home visit'},
                ]
            },
            {
                "table": "agg_child_health",
                "indicators": [
                    {'numerator': 'sum(bf_at_birth)',
                     'denominator': 'sum(born_in_month)',
                     'indicator': 'Early Initiation of Breastfeeding'},
                    {'numerator': 'sum(cf_initiation_in_month)',
                     'denominator': 'sum(cf_initiation_eligible)',
                     'indicator': 'Children initiated appropriate complementary feeding'
                     },
                    {'numerator': 'sum(ebf_in_month)',
                     'denominator': 'sum(ebf_eligible)',
                     'indicator': 'Exclusive breastfeeding'},
                    {'numerator': 'sum(height_measured_in_month)',
                     'denominator': 'sum(height_eligible)',
                     'indicator': 'Height measurement efficiency (in month)'},
                    {'numerator': 'sum(fully_immunized_on_time) + sum(fully_immunized_late)',
                     'denominator': 'sum(fully_immunized_eligible)',
                     'indicator': 'Immunization coverage (at age 1 year)'},
                    {'numerator': 'sum(stunting_moderate) + sum(stunting_severe)',
                     'denominator': 'sum(height_measured_in_month)',
                     'indicator': 'Stunting (height-for-age)'},
                    {'numerator': 'sum(nutrition_status_moderately_underweight)+\
                      sum(nutrition_status_severely_underweight)',
                     'denominator': 'sum(nutrition_status_weighed)',
                     'indicator': 'Underweight Children (weight-for-age)'},
                    {'numerator': 'sum(low_birth_weight_in_month)',
                     'denominator': 'sum(weighed_and_born_in_month)',
                     'indicator': 'Newborns with Low Birth Weight'},
                    {'numerator': 'sum(wasting_moderate)+sum(wasting_severe)',
                     'denominator': 'sum(weighed_and_height_measured_in_month)',
                     'indicator': 'Wasting (weight-for-height)'},
                    {'numerator': 'sum(nutrition_status_weighed)',
                     'denominator': 'sum(wer_eligible)',
                     'indicator': 'Weighing efficiency (Children <5 weighed)'},
                    {'numerator': 'sum(low_birth_weight_in_month)',
                     'denominator': 'sum(weighed_and_born_in_month)',
                     'indicator': 'Newborns with Low Birth Weight'},
                    {'numerator': 'sum(cf_in_month)',
                     'denominator': 'sum(cf_eligible)',
                     'indicator': 'Percentage of children complementary feeding'},
                    {'numerator': 'sum(cf_diet_diversity)',
                     'denominator': 'sum(cf_eligible)',
                     'indicator': 'Percentage of children consuming atleast 4 food groups'},
                    {'numerator': 'sum(cf_diet_quantity)',
                     'denominator': 'sum(cf_eligible)',
                     'indicator': 'Percentage of children consuming adequate food'},
                    {'numerator': 'sum(cf_handwashing)',
                     'denominator': 'sum(cf_eligible)',
                     'indicator': 'Percentage of children whose mothers handwash before feeding'},
                ]
            }


        ]
        return indicator_list
