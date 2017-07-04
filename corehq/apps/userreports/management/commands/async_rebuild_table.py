from __future__ import print_function
from collections import namedtuple

from django.core.management.base import BaseCommand

from corehq.apps.userreports.document_stores import get_document_store
from corehq.apps.userreports.models import AsyncIndicator, get_datasource_config
from corehq.apps.userreports.util import get_indicator_adapter

FakeChange = namedtuple('FakeChange', ['id', 'document'])
CASE_DOC_TYPE = 'CommCareCase'


class Command(BaseCommand):
    help = "Queue a UCR to be built through celery"

    def add_arguments(self, parser):
        parser.add_argument('domain')
        parser.add_argument('data_source_id')
        parser.add_argument('case_type')

    def handle(self, domain, data_source_id, case_type, **options):
        config, _ = get_datasource_config(data_source_id, domain)
        assert config.asynchronous
        fake_change_doc = {'doc_type': CASE_DOC_TYPE, 'domain': domain}

        doc_type = config.referenced_doc_type
        assert doc_type == CASE_DOC_TYPE

        doc_store = get_document_store(domain, doc_type)
        case_accessor = doc_store.case_accessors

        case_ids = case_accessor.get_case_ids_in_domain(type=case_type)
        num_case_ids = len(case_ids)
        print("inserting %d docs" % num_case_ids)
        adapter = get_indicator_adapter(config, can_handle_laboratory=True)
        adapter.build_table()
        # normally called after rebuilding finishes
        adapter.after_build_table()

        for i, case_id in enumerate(case_ids):
            change = FakeChange(case_id, fake_change_doc)
            AsyncIndicator.update_indicators(change, [config._id])
            if i % 1000 == 0:
                print("inserted %d / %d docs" % (i, num_case_ids))
