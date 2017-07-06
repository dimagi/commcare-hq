from __future__ import print_function
import argparse
from collections import namedtuple

from django.core.management.base import BaseCommand
from django.db import connections

from corehq.apps.userreports.models import AsyncIndicator, get_datasource_config


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


class Command(BaseCommand):
    help = "One off for icds"

    def add_arguments(self, parser):
        parser.add_argument('domain')
        parser.add_argument('case_type')

    def handle(self, domain, case_type, **options):
        db_config = DB_CONFIGS[case_type]
        old_config, _ = get_datasource_config(db_config.old_config_id, 'icds-cas')
        new_config, _ = get_datasource_config(db_config.new_config_id, 'icds-cas')
        old_columns = [c.id for c in old_config.get_columns()]
        new_columns = [c.id for c in new_config.get_columns()]
        assert set(old_columns).issubset(set(new_columns))

        async_indicator = (
            AsyncIndicator.objects
            .filter(domain=domain, indicator_config_ids__contains=db_config.old_config_id)
        )

        old_table = db_config.old_table
        new_table = db_config.new_table

        column_string = ','.join(old_columns)

        for ind in async_indicator:
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
                    [ind.doc_id, ind.doc_id]
                )
            ind.indicator_config_ids = ind.indicator_config_ids.remove(db_config.old_config_id)
            ind.save()
