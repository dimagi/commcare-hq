from __future__ import absolute_import, print_function
from __future__ import unicode_literals

from django.core.management.base import BaseCommand

import dateutil
from corehq.sql_db.connections import get_icds_ucr_db_alias
from django.db import connections


class Command(BaseCommand):

    def add_arguments(self, parser):
        parser.add_argument(
            'input_month'
        )

    def handle(self, input_month, *args, **options):
        indicator_list = self.get_indicator_list()
        indicator_ratio = []

        for indicator in indicator_list:
            input_month = dateutil.parser.parse(input_month).date().replace(day=1).__str__()
            query = self.prepare_query(indicator, input_month)
            ratio_check = self.execute_query(query)
            ratio_check = [(indicator["indicators"][i]['numerator'], res) for i, res in enumerate(ratio_check)]
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
        indicators = ""
        for indicator in indicator_dict['indicators']:
            indicators += "({numerator})>({denominator}),".format(**indicator)

        query_param['indicators'] = indicators[:-1]
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
                    {'numerator': 'sum(num_launched_awcs)', 'denominator': 'sum(num_awcs)'},
                    {'numerator': 'sum(cases_person_has_aadhaar)',
                     'denominator': 'sum(cases_person_beneficiary)'},
                    {'numerator': 'sum(cases_child_health)', 'denominator': 'sum(cases_child_health_all)'},
                    {'numerator': 'sum(cases_ccs_pregnant)', 'denominator': 'sum(cases_ccs_pregnant_all)'},
                    {'numerator': 'sum(cases_ccs_lactating)', 'denominator': 'sum(cases_ccs_lactating_all)'},
                    {'numerator': 'sum(infra_clean_water)', 'denominator': 'sum(num_awc_infra_last_update)'},
                    {'numerator': 'sum(infra_functional_toilet)',
                     'denominator': 'sum(num_awc_infra_last_update)'},
                    {'numerator': 'sum(infra_medicine_kits)', 'denominator': 'sum(num_awc_infra_last_update)'},
                    {'numerator': 'sum(infra_infant_weighing_scale)',
                     'denominator': 'sum(num_awc_infra_last_update)'},
                    {'numerator': 'sum(infra_adult_weighing_scale)',
                     'denominator': 'sum(num_awc_infra_last_update)'},
                ],
            },
            {
                "table": "agg_ccs_record",
                "indicators": [
                    {'numerator': 'sum(institutional_delivery_in_month)',
                     'denominator': 'sum(delivered_in_month)',},
                    {'numerator': 'sum(anc1_received_at_delivery)', 'denominator': 'sum(delivered_in_month)',
                     },
                    {'numerator': 'sum(anc2_received_at_delivery)', 'denominator': 'sum(delivered_in_month)',
                     },
                    {'numerator': 'sum(anc3_received_at_delivery)', 'denominator': 'sum(delivered_in_month)',
                     },
                    {'numerator': 'sum(anc4_received_at_delivery)', 'denominator': 'sum(delivered_in_month)',
                     },
                    {'numerator': '(sum(anemic_moderate) + sum(anemic_severe))', 'denominator': 'sum(pregnant)',
                     },
                    {'numerator': 'sum(tetanus_complete)', 'denominator': 'sum(pregnant)'},
                    {'numerator': 'sum(resting_during_pregnancy)', 'denominator': 'sum(pregnant)'},
                    {'numerator': 'sum(extra_meal)', 'denominator': 'sum(pregnant)'},
                    {'numerator': 'sum(counsel_immediate_bf)', 'denominator': 'sum(trimester_3)'},
                ]
            },
            {
                "table": "agg_child_health",
                "indicators": [
                    {'numerator': 'sum(bf_at_birth)', 'denominator': 'sum(born_in_month)'},
                    {'numerator': 'sum(cf_initiation_in_month)', 'denominator': 'sum(cf_initiation_eligible)',
                     },
                    {'numerator': 'sum(ebf_in_month)', 'denominator': 'sum(ebf_eligible)', },
                    {'numerator': 'sum(height_measured_in_month)', 'denominator': 'sum(height_eligible)'},
                    {'numerator': 'sum(fully_immunized_on_time) + sum(fully_immunized_late)',
                     'denominator': 'sum(fully_immunized_eligible)', },
                    {'numerator': 'sum(stunting_moderate) + sum(stunting_severe)',
                     'denominator': 'sum(height_measured_in_month)'},
                    {'numerator': 'sum(nutrition_status_moderately_underweight)+\
                      sum(nutrition_status_severely_underweight)',
                     'denominator': 'sum(nutrition_status_weighed)'},
                    {'numerator': 'sum(low_birth_weight_in_month)',
                     'denominator': 'sum(weighed_and_born_in_month)'},
                    {'numerator': 'sum(wasting_moderate)+sum(wasting_severe)',
                     'denominator': 'sum(weighed_and_height_measured_in_month)'},
                    {'numerator': 'sum(nutrition_status_weighed)', 'denominator': 'sum(wer_eligible)'},
                    {'numerator': 'sum(low_birth_weight_in_month)',
                     'denominator': 'sum(weighed_and_born_in_month)',
                     },
                    {'numerator': 'sum(cf_in_month)', 'denominator': 'sum(cf_eligible)',
                     },
                    {'numerator': 'sum(cf_diet_diversity)', 'denominator': 'sum(cf_eligible)',
                     },
                    {'numerator': 'sum(cf_diet_quantity)', 'denominator': 'sum(cf_eligible)',
                     },
                    {'numerator': 'sum(cf_handwashing)', 'denominator': 'sum(cf_eligible)',
                     },
                ]
            }


        ]
        return indicator_list
