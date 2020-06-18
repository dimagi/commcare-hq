import dateutil

from django.core.management.base import BaseCommand
from django.db import connections

from dateutil.relativedelta import relativedelta
from corehq.apps.userreports.util import get_table_name
from corehq.sql_db.connections import get_icds_ucr_citus_db_alias
from custom.icds_reports.const import AGG_MIGRATION_TABLE


class Command(BaseCommand):

    def add_arguments(self, parser):
        parser.add_argument('domain')
        parser.add_argument(
            'input_month'
        )

    def handle(self, domain, input_month, *args, **options):
        messages = [
            'ccs cases migrated count for month of {} is {}',
            'child health cases migrated count for month of {} is {}',
            'ccs cases closed count for month of {} is {}',
            'child health cases closed count for month of {} is {}',
                    ]
        input_month = str(dateutil.parser.parse(input_month).date().replace(day=1))
        next_month = str(dateutil.parser.parse(input_month).date() + relativedelta(months=1))
        queries = self.prepare_queries(domain, input_month, next_month)

        for index, query in enumerate(queries):
            count = self.execute_query(query)
            print(messages[index].format(input_month, count[0]))

    def execute_query(self, query):
        db_alias = get_icds_ucr_citus_db_alias()
        with connections[db_alias].cursor() as cursor:
            cursor.execute(query)
            return cursor.fetchall()[0]

    def prepare_queries(self, domain, input_month, next_month):
        queries_list = []
        query_param = dict()
        query_param['agg_migration'] = AGG_MIGRATION_TABLE
        query_param['input_month'] = input_month
        query_param['next_month'] = next_month
        query_param['child_health_ucr'] = get_table_name(domain, 'static-child_health_cases')
        query_param['ccs_ucr'] = get_table_name(domain, 'static-ccs_record_cases')

        ccs_mig_query = """
        select  count(*) from  ccs_record_monthly ccs inner join "{agg_migration}" mig on ccs.supervisor_id = mig.supervisor_id and
         ccs.person_case_id=mig.person_case_id and mig.month='{input_month}' where mig.migration_date < '{next_month}' and 
         mig.migration_date >= '{input_month}' and mig.is_migrated = 1 
        """.format(**query_param)
        queries_list.append(ccs_mig_query)

        chm_mig_query = """
        select count(*) from child_health_monthly chm inner join "{agg_migration}" mig on chm.supervisor_id = mig.supervisor_id and
         chm.child_person_case_id=mig.person_case_id and mig.month = '{input_month}' where mig.migration_date < '{next_month}' and 
         mig.migration_date >= '{input_month}'and mig.is_migrated = 1
        """.format(**query_param)
        queries_list.append(chm_mig_query)

        ccs_closed_query = """
        select  count(*) from  ccs_record_monthly ccs inner join "{ccs_ucr}" ccs_ucr on ccs.supervisor_id = ccs_ucr.supervisor_id and
         ccs.person_case_id=ccs_ucr.person_case_id and ccs.month = '{input_month}' where ccs_ucr.closed_on >= '{input_month}' and ccs_ucr.closed_on < '{next_month}'
        """.format(**query_param)
        queries_list.append(ccs_closed_query)

        chm_closed_query = """
        select  count(*) from  child_health_monthly chm inner join "{child_health_ucr}" chm_ucr on chm.supervisor_id = chm_ucr.supervisor_id and 
        chm.child_person_case_id = chm_ucr.mother_id and chm.month = '{input_month}' where chm_ucr.closed_on >= '{input_month}' and chm_ucr.closed_on < '{next_month}'
        """.format(**query_param)
        queries_list.append(chm_closed_query)

        return queries_list
