from django.core.management.base import BaseCommand
from collections import namedtuple

from corehq.apps.userreports.models import AsyncIndicator, get_datasource_config
from corehq.apps.userreports.util import get_indicator_adapter


DOMAIN = 'icds-cas'
DATA_SOURCES = (
    'static-icds-cas-static-child_cases_monthly_tableau_v2',
    'static-icds-cas-static-ccs_record_cases_monthly_tableau_v2',
)
FakeChange = namedtuple('FakeChange', ['id', 'document'])
CASE_DOC_TYPE = 'CommCareCase'


STATE_IDS = [
    'f98e91aa003accb7b849a0f18ebd7039',
    'f9b47ea2ee2d8a02acddeeb491d3e175',
    'a2fcb186e9be8464e167bb1c56ce8fd9',
    'f1cd643f0df908421abd915298ba57bc',
    'd982a6fb4cca0824fbde59db18d3800f',
    '9cd4fd88d9f047088a377b7e7d144830',
    'ea4d587fa93a2ed8300853d51db661ef',
]


class Command(BaseCommand):
    help = ""

    def handle(self, *args, **options):
        fake_change_doc = {'doc_type': CASE_DOC_TYPE, 'domain': DOMAIN}

        for data_source_id in DATA_SOURCES:
            print("processing data source %s" % data_source_id)
            data_source, is_static = get_datasource_config(data_source_id, DOMAIN)
            assert is_static
            adapter = get_indicator_adapter(data_source)
            table = adapter.get_table()
            for case_id in self._get_case_ids_to_process(adapter, table, data_source_id):
                change = FakeChange(case_id, fake_change_doc)
                AsyncIndicator.update_from_kafka_change(change, [data_source_id])

    def _add_filters(self, query, table, data_source_id):
        if data_source_id == 'static-icds-cas-static-child_cases_monthly_tableau_v2':
            return query.filter(
                table.columns.valid_all_registered_in_month == 1,
                table.columns.valid_in_month == 0,
            )
        elif data_source_id == 'static-icds-cas-static-ccs_record_cases_monthly_tableau_v2':
            return query.filter(
                table.columns.pregnant_all == 1,
                table.columns.pregnant == 0,
            )

    def _get_case_ids_to_process(self, adapter, table, data_source_id):
        for state_id in STATE_IDS:
            print("processing state %s" % state_id)
            query = adapter.session_helper.Session.query(table.columns.doc_id).distinct(table.columns.doc_id)
            case_ids = query.filter(
                table.columns.state_id == state_id,
            )
            case_ids = self._add_filters(query, table, data_source_id).all()

            num_case_ids = len(case_ids)
            print("processing %d cases" % (num_case_ids))
            for i, case_id in enumerate(case_ids):
                yield case_id
                if i % 1000 == 0:
                    print("processed %d / %d docs" % (i, num_case_ids))
