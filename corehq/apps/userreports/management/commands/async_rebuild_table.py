from __future__ import print_function
from __future__ import absolute_import
import argparse
from collections import namedtuple

from django.core.management.base import BaseCommand

from corehq.form_processor.models import CommCareCaseSQL
from corehq.apps.userreports.models import AsyncIndicator, get_datasource_config
from corehq.apps.userreports.util import get_indicator_adapter

FakeChange = namedtuple('FakeChange', ['id', 'document'])
CASE_DOC_TYPE = 'CommCareCase'


class Command(BaseCommand):
    help = "Queue a UCR to be built through celery"

    def add_arguments(self, parser):
        parser.add_argument('domain')
        parser.add_argument('case_type')
        parser.add_argument('data_source_ids', nargs=argparse.REMAINDER)

    def handle(self, domain, case_type, data_source_ids, **options):
        configs = []
        for data_source_id in data_source_ids:
            config, _ = get_datasource_config(data_source_id, domain)
            assert config.asynchronous
            assert config.referenced_doc_type == CASE_DOC_TYPE
            configs.append(config)

        fake_change_doc = {'doc_type': CASE_DOC_TYPE, 'domain': domain}

        for config in configs:
            adapter = get_indicator_adapter(config, can_handle_laboratory=True)
            adapter.build_table()
            # normally called after rebuilding finishes
            adapter.after_table_build()

        self.domain = domain
        self.case_type = case_type

        config_ids = [config._id for config in configs]
        for case_id in self._get_case_ids_to_process():
            change = FakeChange(case_id, fake_change_doc)
            AsyncIndicator.update_from_kafka_change(change, config_ids)

        for config in configs:
            if not config.is_static:
                config.meta.build.rebuilt_asynchronously = True
                config.save()


    def _get_case_ids_to_process(self):
        from corehq.sql_db.util import get_db_aliases_for_partitioned_query
        dbs = get_db_aliases_for_partitioned_query()
        for db in dbs:
            case_ids = (
                CommCareCaseSQL.objects
                .using(db)
                .filter(domain=self.domain, type=self.case_type)
                .values_list('case_id', flat=True)
            )
            num_case_ids = len(case_ids)
            print("processing %d docs from db %s" % (num_case_ids, db))
            for i, case_id in enumerate(case_ids):
                yield case_id
                if i % 1000 == 0:
                    print("processed %d / %d docs from db %s" % (i, num_case_ids, db))
