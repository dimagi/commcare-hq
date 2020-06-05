from datetime import date

import time
from django.core.management.base import BaseCommand

from django.db import connections, transaction
from corehq.apps.userreports.util import get_table_name
from corehq.sql_db.connections import get_icds_ucr_citus_db_alias
from corehq.apps.userreports.tasks import _get_config_by_id, _build_indicators
from corehq.apps.change_feed.data_sources import get_document_store_for_doc_type
from pillowtop.dao.couch import ID_CHUNK_SIZE

@transaction.atomic
def _run_custom_sql_script(command):
    db_alias = get_icds_ucr_citus_db_alias()
    if not db_alias:
        return

    with connections[db_alias].cursor() as cursor:
        cursor.execute(command)

    return cursor.fetchall()

class Command(BaseCommand):
    DOMAIN_NAME = 'icds-dashboard-qa'
    UCR_NAMES = [
        'static-child_health_cases',
        'static-ccs_record_cases',
        'static-person_cases_v3',
        'static-household_cases',
        'static-child_tasks_cases',
        'static-pregnant-tasks_cases',
    ]

    def add_arguments(self, parser):
        parser.add_argument('ucr_name')

    def handle(self, ucr_name, *args, **options):

        for ucr in self.UCR_NAMES:
            if ucr != ucr_name:
                continue

            print(f"PROCESSING : {ucr}")
            self.dump_duplicate_records(ucr)
            self.remove_duplicates(ucr)
            self.reprocess_cases(ucr)

    def get_ucr_config_and_document_store(self, indicator_config_id):
        config = _get_config_by_id(indicator_config_id)
        document_store = get_document_store_for_doc_type(
            config.domain, config.referenced_doc_type,
            case_type_or_xmlns=config['configured_filter']['property_value'],
        )
        return config, document_store

    @property
    def temp_duplicate_table_name(self,ucr_name):
        today = date.today().strftime('%Y-%m-%d')
        return f"temp_duplicate_{ucr_name}_{today}"

    def dump_duplicate_records(self, ucr_name):
        ucr_table_name = get_table_name(self.DOMAIN_NAME, ucr_name)

        delete_existing_temp = "DROP TABLE IF EXISTS {self.temp_duplicate_table_name}"
        _run_custom_sql_script(delete_existing_temp)

        query = f"""
            CREATE TABLE {self.temp_duplicate_table_name} AS (
                SELECT doc_id, count(*) from {ucr_table_name} group by doc_id order by count
            )
        """
        _run_custom_sql_script(query)

    def remove_duplicates(self, ucr_name):
        ucr_table_name = get_table_name(self.DOMAIN_NAME, ucr_name)
        query = f"""
        delete from {ucr_table_name} where doc_id in
        (select doc_id from {self.temp_duplicate_table_name} where count>1)
        """
        _run_custom_sql_script(query)

    def reprocess_cases(self, ucr):
        config_id = f'static-{self.DOMAIN_NAME}-{ucr}'
        config, document_store = self.get_ucr_config_and_document_store(config_id)

        query = f"select doc_id from {self.temp_duplicate_table_name} where count>1"
        doc_ids = _run_custom_sql_script(query)
        doc_ids = [doc_id[0] for doc_id in doc_ids]

        self.build_indicator(doc_ids, config, document_store)

    def build_indicator(self, doc_ids, config, document_store):
        relevant_ids = list()
        next_event = time.time() + 10
        for doc_id in doc_ids:
            relevant_ids.append(doc_id)
            if len(relevant_ids) >= ID_CHUNK_SIZE:
                _build_indicators(config, document_store, relevant_ids)
                relevant_ids = []

            if time.time() > next_event:
                print("processed till case %s" % (doc_id))
                next_event = time.time() + 10

        if relevant_ids:
            _build_indicators(config, document_store, relevant_ids)
