
from datetime import date
from dateutil import parser
import csv
from django.core.management.base import BaseCommand

from django.db import connections

from corehq.sql_db.connections import get_icds_ucr_citus_db_alias
from custom.icds_reports.models.aggregate import AwcLocation
from dimagi.utils.chunked import chunked
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors

db_alias = get_icds_ucr_citus_db_alias()


def _run_custom_sql_script(command):
    with connections[db_alias].cursor() as cursor:
        cursor.execute(command)
        return cursor.fetchall()


class Command(BaseCommand):
    def handle(self, *args, **options):
        state_locations = AwcLocation.objects.filter(aggregation_level=1, state_is_test=0).values('state_id',
                                                                                                  'state_name')
        final_state_data = {
            location['state_id']: {
                'state_name': location['state_name'],
                36: 0,
                48: 0,
                60: 0,
                72: 0
            }
            for location in state_locations
        }

        query = """
                    SELECT
                        ucr.state_id,
                        ucr.mother_id
                    FROM  child_health_monthly
                    INNER JOIN "ucr_icds-cas_static-child_health_cases_a46c129f" ucr
                    ON (
                        child_health_monthly.case_id=ucr.doc_id AND
                        child_health_monthly.supervisor_id=ucr.supervisor_id
                    )
                    WHERE
                        pse_eligible=1 AND
                        age_tranche='{age_group}' AND
                        month>='2020-01-01' AND
                        month<'2020-04-01';
                """

        case_accessor = CaseAccessors('icds-cas')

        for age_group in (36, 48, 60, 72):

            case_id_to_state_id = {item[1]: item[0]
                                   for item in _run_custom_sql_script(query.format(age_group=age_group))
                                   }

            for ids_chunk in chunked(list(case_id_to_state_id.keys()), 500000):
                for case in case_accessor.get_cases(list(ids_chunk)):
                    date_return_private = case.get_case_property('date_return_private')
                    if (date_return_private and
                            date(2020, 1, 1) <= parser.parse(date_return_private) < date(2020, 4, 1)):
                        final_state_data[case_id_to_state_id[case.case_id]][age_group] += 1

        self.write_to_file(final_state_data)

    def write_to_file(self, state_json_data):
        with open('preschool_quarter_data.csv', 'w') as fout:
            writer = csv.writer(fout)
            state_data_in_list = [
                'state_name',
                '3_4',
                '4_5',
                '5_6'
            ]
            for state_id, state_data in state_json_data.items():
                state_data_in_list.append([
                    state_data['state_name'],
                    state_data[36] + state_data[48],
                    state_data[60],
                    state_data[72]
                ])

            writer.writeLines(state_data_in_list)
