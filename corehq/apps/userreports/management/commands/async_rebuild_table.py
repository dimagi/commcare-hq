from __future__ import print_function
from __future__ import absolute_import
from __future__ import unicode_literals
import argparse
from collections import namedtuple

from django.core.management.base import BaseCommand

from corehq.form_processor.models import CommCareCaseSQL, XFormInstanceSQL
from corehq.apps.userreports.models import AsyncIndicator, get_datasource_config
from corehq.apps.userreports.util import get_indicator_adapter

FakeChange = namedtuple('FakeChange', ['id', 'document'])
CASE_DOC_TYPE = 'CommCareCase'
XFORM_DOC_TYPE = 'XFormInstance'


class Command(BaseCommand):
    help = "Queue a UCR to be built through celery"

    def add_arguments(self, parser):
        parser.add_argument('domain')
        parser.add_argument('type', help="either xform or case")
        parser.add_argument('case_type_or_xmlns')
        parser.add_argument('data_source_ids', nargs=argparse.REMAINDER)

    def handle(self, domain, type_, case_type_or_xmlns, data_source_ids, **options):
        assert type_ in ('xform', 'case')
        self.referenced_type = CASE_DOC_TYPE if type_ == 'case' else XFORM_DOC_TYPE

        configs = []
        for data_source_id in data_source_ids:
            config, _ = get_datasource_config(data_source_id, domain)
            assert config.asynchronous
            assert config.referenced_doc_type == self.referenced_type
            configs.append(config)

        fake_change_doc = {'doc_type': self.referenced_type, 'domain': domain}

        for config in configs:
            adapter = get_indicator_adapter(config, can_handle_laboratory=True)
            adapter.build_table()
            # normally called after rebuilding finishes
            adapter.after_table_build()

        self.domain = domain
        self.case_type_or_xmlns = case_type_or_xmlns

        config_ids = [config._id for config in configs]
        for id_ in self._get_ids_to_process():
            change = FakeChange(id_, fake_change_doc)
            AsyncIndicator.update_from_kafka_change(change, config_ids)

        for config in configs:
            if not config.is_static:
                config.meta.build.rebuilt_asynchronously = True
                config.save()

    def _get_ids_to_process(self):
        from corehq.sql_db.util import get_db_aliases_for_partitioned_query
        dbs = get_db_aliases_for_partitioned_query()
        for db in dbs:
            ids_ = self._get_ids(db)
            num_ids = len(ids_)
            print("processing %d docs from db %s" % (num_ids, db))
            for i, id_ in enumerate(ids_):
                yield id_
                if i % 1000 == 0:
                    print("processed %d / %d docs from db %s" % (i, num_ids, db))

    def _get_ids(self, db):
        if self.referenced_type == CASE_DOC_TYPE:
            return (
                CommCareCaseSQL.objects
                .using(db)
                .filter(domain=self.domain, type=self.case_type_or_xmlns)
                .values_list('case_id', flat=True)
            )
        elif self.referenced_type == XFORM_DOC_TYPE:
            return(
                XFormInstanceSQL.objects
                .using(db)
                .filter(domain=self.domain, xmlns=self.case_type_or_xmlns)
                .values_list('form_id', flat=True)
            )
