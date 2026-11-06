from __future__ import absolute_import, print_function
from __future__ import unicode_literals

from django.core.management.base import BaseCommand
from django.db import connections

from corehq.apps.change_feed.data_sources import get_document_store_for_doc_type
from corehq.apps.userreports.exceptions import ValidationError
from corehq.apps.userreports.models import StaticDataSourceConfiguration
from corehq.apps.userreports.specs import EvaluationContext
from corehq.apps.userreports.util import get_indicator_adapter
from corehq.sql_db.connections import get_icds_ucr_db_alias
from corehq.util.log import with_progress_bar
from custom.icds_reports.const import DISTRIBUTED_TABLES, DASHBOARD_DOMAIN


class Command(BaseCommand):

    def add_arguments(self, parser):
        parser.add_argument('action', choices=('stats', 'clean', 'reprocess'))

    def handle(self, action, **options):
        if action == 'stats':
            with connections[get_icds_ucr_db_alias()].cursor() as cursor:
                for table, col in DISTRIBUTED_TABLES:
                    cursor.execute('select count(*) from "{}" where {} is null'.format(table, col))
                    print(table, cursor.fetchone()[0])

        for config in StaticDataSourceConfiguration.by_domain(DASHBOARD_DOMAIN):
            if config.sql_settings.citus_config.distribution_type != 'hash':
                continue

            adapter = get_indicator_adapter(config)
            table_name = adapter.get_table().name
            with adapter.engine.begin() as con:
                col = config.sql_settings.citus_config.distribution_column
                res = con.execute('select doc_id from "{}" where {} is null'.format(table_name, col))
                null_docs = list({row[0] for row in res})

            print(table_name, len(null_docs))
            if not null_docs or action == 'stats':
                continue

            document_store = get_document_store_for_doc_type(
                config.domain, config.referenced_doc_type,
                load_source="build_indicators",
            )
            for doc in document_store.iter_documents(with_progress_bar(null_docs)):
                if action == 'clean':
                    eval_context = EvaluationContext(doc)

                    if config.has_validations:
                        try:
                            config.validate_document(doc, eval_context)
                        except ValidationError:
                            adapter.delete(doc)
                elif action == 'reprocess':
                    adapter.best_effort_save(doc)
