from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

from copy import copy

from django.core.management import call_command
from django.core.management.base import BaseCommand

from corehq.apps.userreports.models import StaticDataSourceConfiguration
from corehq.apps.userreports.sql import IndicatorSqlAdapter
from corehq.sql_db.connections import connection_manager
from custom.icds_reports.const import DASHBOARD_DOMAIN


class Command(BaseCommand):

    def add_arguments(self, parser):
        parser.add_argument('engine_id')

    def handle(self, engine_id, **options):
        db_alias = connection_manager.get_django_db_alias(engine_id)

        call_options = copy(options)
        call_options['database'] = db_alias
        call_command(
            'migrate',
            **call_options
        )

        for ds in StaticDataSourceConfiguration.by_domain(DASHBOARD_DOMAIN):
            if engine_id == ds.engine_id or engine_id in ds.mirrored_engine_ids:
                adapter = IndicatorSqlAdapter(ds, engine_id=engine_id)
                adapter.build_table()
