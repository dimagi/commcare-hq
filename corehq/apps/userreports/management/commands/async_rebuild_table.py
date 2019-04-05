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
        parser.add_argument('type_', help="either xform or case")
        parser.add_argument('case_type_or_xmlns')
        parser.add_argument('data_source_ids', nargs=argparse.REMAINDER)
        parser.add_argument('--bulk', action='store_true', dest='bulk',
                            help='bulk create. Only use if you know the implications')
        parser.add_argument('--database', action='store', dest='database',
                            help='Only retrieve from one database')
        parser.add_argument('--initiated-by', action='store', required=True, dest='initiated',
                            help='Who initiated the rebuild')

    def handle(self, domain, type_, case_type_or_xmlns, data_source_ids, **options):
        assert type_ in ('xform', 'case')
        self.referenced_type = CASE_DOC_TYPE if type_ == 'case' else XFORM_DOC_TYPE

        configs = []
        for data_source_id in data_source_ids:
            config, _ = get_datasource_config(data_source_id, domain)
            assert config.asynchronous
            assert config.referenced_doc_type == self.referenced_type
            configs.append(config)

        for config in configs:
            adapter = get_indicator_adapter(config)
            adapter.build_table(initiated_by=options['initiated'], source='async_rebuild_table')

        self.domain = domain
        self.case_type_or_xmlns = case_type_or_xmlns
        self.bulk = options['bulk']
        self.database = options['database']

        self.config_ids = [config._id for config in configs]
        ids = []
        for id_ in self._get_ids_to_process():
            ids.append(id_)
            if len(ids) > 999:
                self._save_ids(ids)
                ids = []

        self._save_ids(ids)

        for config in configs:
            if not config.is_static:
                config.meta.build.rebuilt_asynchronously = True
                config.save()

    @property
    def fake_change_doc(self):
        return {'doc_type': self.referenced_type, 'domain': self.domain}

    def _save_ids(self, ids):
        if self.bulk:
            AsyncIndicator.bulk_creation(ids, self.referenced_type, self.domain, self.config_ids)
        else:
            for id_ in ids:
                change = FakeChange(id_, self.fake_change_doc)
                AsyncIndicator.update_from_kafka_change(change, self.config_ids)

    def _get_ids_to_process(self):
        from corehq.sql_db.util import get_db_aliases_for_partitioned_query
        dbs = get_db_aliases_for_partitioned_query()
        if self.database:
            dbs = [db for db in dbs if db == self.database]
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
