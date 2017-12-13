from __future__ import print_function
from __future__ import absolute_import
from collections import namedtuple

from django.core.management.base import BaseCommand
from django.db import connections

from corehq.apps.userreports.models import get_datasource_config


COMMON_PERSON_COLUMNS = ()
COMMON_CHILD_HEALTH_COLUMNS = ()
COMMON_CCS_RECORD_COLUMNS = ()

DbConfig = namedtuple(
    'DbConfig',
    ['old_table', 'new_table', 'old_config_id', 'new_config_id', 'has_repeat_iteration']
)

PERSON_DBS = DbConfig(
    'config_report_icds-cas_static-person_cases_60bd77e9',
    'config_report_icds-cas_static-person_cases_v2_b4b5d57a',
    'static-icds-cas-static-person_cases',
    'static-icds-cas-static-person_cases_v2',
    False
)

CHILD_HEALTH_DBS = DbConfig(
    'config_report_icds-cas_static-child_cases_monthly_tabl_d4032f37',
    'config_report_icds-cas_static-child_cases_monthly_tabl_551fd064',
    'static-icds-cas-static-child_cases_monthly_tableau',
    'static-icds-cas-static-child_cases_monthly_tableau_v2',
    True
)

CCS_RECORD_DBS = DbConfig(
    'config_report_icds-cas_static-ccs_record_cases_monthly_33021c88',
    'config_report_icds-cas_static-ccs_record_cases_monthly_d0e2e49e',
    'static-icds-cas-static-ccs_record_cases_monthly_tableau',
    'static-icds-cas-static-ccs_record_cases_monthly_tableau_v2',
    True
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
        parser.add_argument(
            '--real-run',
            action='store_false',
            dest='dry_run',
            default=True,
            help="Don't do a dry run",
        )

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

        self.old_table = db_config.old_table
        self.new_table = db_config.new_table

        # create a column string
        quoted_columns = []
        for col in old_columns:
            if col.islower():
                quoted_columns.append('%s' % col)
            else:
                quoted_columns.append('"%s"' % col)
        self.column_string = ', '.join(quoted_columns)
        self.select_column_string = ', '.join(['A.' + col for col in quoted_columns])

        sql_command = self._sql_command(db_config.has_repeat_iteration)

        if options['dry_run']:
            print(sql_command)
        else:
            print("count of old table %s: " % self.old_table)
            print(self.get_count(self.old_table))
            print("count of new table %s: " % self.new_table)
            print(self.get_count(self.new_table))
            with connections['icds-ucr'].cursor() as cursor:
                cursor.execute(sql_command)
            print("count of new table %s: " % self.new_table)
            print(self.get_count(self.new_table))

    def get_count(self, table_name):
        with connections['icds-ucr'].cursor() as cursor:
            table = '"%s"' % table_name
            cursor.execute(
                'SELECT count(*) from ' + table
            )
            return cursor.fetchone()

    def _sql_command(self, has_repeat_iteration):
        if has_repeat_iteration:
            join = 'A.doc_id = B.doc_id AND A.repeat_iteration = B.repeat_iteration '
        else:
            join = 'A.doc_id = B.doc_id'

        old_table = '"%s"' % self.old_table
        new_table = '"%s"' % self.new_table

        return (
           " INSERT INTO " + new_table + " ( " + self.column_string + " ) " +
           " SELECT " + self.select_column_string + " " +
           " FROM " + old_table + " A " +
           " LEFT JOIN " + new_table + " B " +
           " ON " + join + " " +
           " WHERE B.doc_id IS NULL "
       )
