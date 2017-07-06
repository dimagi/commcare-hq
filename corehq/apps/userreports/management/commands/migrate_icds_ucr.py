from __future__ import print_function
from collections import namedtuple

from django.core.management.base import BaseCommand
from django.db import connections

from corehq.apps.es import CaseES
from corehq.apps.userreports.models import get_datasource_config
from corehq.form_processor.models import CommCareCaseSQL
from corehq.util.log import with_progress_bar


COMMON_PERSON_COLUMNS = ()
COMMON_CHILD_HEALTH_COLUMNS = ()
COMMON_CCS_RECORD_COLUMNS = ()

DbConfig = namedtuple('DbConfig', ['old_table', 'new_table', 'old_config_id', 'new_config_id'])

PERSON_DBS = DbConfig(
    'config_report_icds-cas_static-person_cases_60bd77e9',
    'config_report_icds-cas_static-person_cases_v2_b4b5d57a',
    'static-icds-cas-static-person_cases',
    'static-icds-cas-static-person_cases_v2',
)

CHILD_HEALTH_DBS = DbConfig(
    'config_report_icds-cas_static-child_cases_monthly_tabl_d4032f37',
    'config_report_icds-cas_static-child_cases_monthly_tabl_551fd064',
    'static-icds-cas-static-child_cases_monthly_tableau',
    'static-icds-cas-static-child_cases_monthly_tableau_v2',
)

CCS_RECORD_DBS = DbConfig(
    'config_report_icds-cas_static-ccs_record_cases_monthly_33021c88',
    'config_report_icds-cas_static-ccs_record_cases_monthly_d0e2e49e',
    'static-icds-cas-static-ccs_record_cases_monthly_tableau',
    'static-icds-cas-static-ccs_record_cases_monthly_tableau_v2',
)

DB_CONFIGS = {
    'child_health': CHILD_HEALTH_DBS,
    'ccs_record': CCS_RECORD_DBS,
    'person': PERSON_DBS,
}

DOMAIN = 'icds-cas'


class Command(BaseCommand):
    help = "One off for icds"

    def add_arguments(self, parser):
        parser.add_argument('case_type')

    def handle(self, case_type, **options):
        # get the configurations for the case type
        db_config = DB_CONFIGS[case_type]
        old_config, _ = get_datasource_config(db_config.old_config_id, DOMAIN)
        new_config, _ = get_datasource_config(db_config.new_config_id, DOMAIN)
        old_columns = [c.id for c in old_config.get_columns()]
        new_columns = [c.id for c in new_config.get_columns()]

        # verify that the old columns are subset of the new columns
        # new columns are allowed to be null
        assert set(old_columns).issubset(set(new_columns))

        old_table = db_config.old_table
        new_table = db_config.new_table

        # create a column string
        column_string = ','.join(old_columns)
        total_cases = self.total_cases(case_type)

        for case_id in with_progress_bar(self._get_case_ids_to_process(case_type), total_cases):
            with connections['icds-ucr'].cursor() as cursor:
                cursor.execute(
                    "INSERT INTO " + new_table + " " +
                    " (" + column_string + ") " +
                    "SELECT " + column_string + " from " + old_table + " " +
                    "WHERE " +
                    "    doc_id = %s AND " +
                    "    NOT EXISTS ( " +
                    "        SELECT doc_id FROM " + new_table + "WHERE doc_id = %s " +
                    "    ) ",
                    [case_id, case_id]
                )

    def total_cases(self, case_type):
        return CaseES().domain(DOMAIN).case_type(case_type).count()

    def _get_case_ids_to_process(self, case_type):
        # generator to return case ids for a certain type
        from corehq.sql_db.util import get_db_aliases_for_partitioned_query
        dbs = get_db_aliases_for_partitioned_query()
        for db in dbs:
            case_ids = (
                CommCareCaseSQL.objects
                .using(db)
                .filter(domain=DOMAIN, type=case_type)
                .values_list('case_id', flat=True)
            )
            for case_id in case_ids:
                yield case_id
