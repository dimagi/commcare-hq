import time

from django.core.management.base import BaseCommand
from django.db import connections

from corehq.apps.userreports.tasks import _build_indicators
from corehq.apps.userreports.util import get_table_name
from corehq.sql_db.connections import get_icds_ucr_citus_db_alias
from pillowtop.dao.couch import ID_CHUNK_SIZE



class Command(BaseCommand):
    help = "Rebuild open child tasks"

    def add_arguments(self, parser):
        parser.add_argument('domain')

    def handle(self, domain):
        child_tasks_record_config, child_tasks_record_document_store =\
            self.get_ucr_config_and_document_store('static-child_tasks_cases', 'child_tasks')
        query = self.get_query(domain)
        with connections[get_icds_ucr_citus_db_alias()].cursor() as cursor:
            cursor.execute(query)
            awc_ids = [row['awc_id'] for row in cursor.fetchall()]
        _build_indicators(awc_ids, child_tasks_record_config, child_tasks_record_document_store)

    def get_query(self, domain):
        dates = tuple('2019-11-01', '2019-12-01')
        sql = """WITH ucr_child_tasks_table AS (SELECT child_health_case_id FROM "{ucr_tablename}") 
        SELECT DISTINCT child_health_monthly.awc_id FROM ucr_child_tasks_table INNER JOIN child_health_monthly on
         ucr_child_tasks_table.child_health_case_id = child_health_monthly.case_id WHERE 
         child_health_monthly.open_in_month = 1 AND child_health_monthly.month IN {dates}
            """.format(
            ucr_tablename = get_table_name(domain, 'static-child_tasks_cases'),
            dates = dates
        )
        return sql

    def build_indicator(self, doc_ids, config, document_store):
        config.asynchronous = True #build through async queue
        relevant_ids = list()
        next_event = time.time() + 10
        for doc_id in doc_ids:
            relevant_ids.append(doc_id)
            if len(relevant_ids) >= ID_CHUNK_SIZE:
                _build_indicators(config, document_store, relevant_ids)
                relevant_ids = []

            if time.time() > next_event:
                print("processed till case %s" % (doc_id['case_id']))
                next_event = time.time() + 10

        if relevant_ids:
            _build_indicators(config, document_store, relevant_ids)
