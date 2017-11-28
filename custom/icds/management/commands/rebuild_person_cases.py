from __future__ import absolute_import
from django.core.management.base import BaseCommand

from corehq.apps.userreports.models import AsyncIndicator, get_datasource_config
from corehq.apps.userreports.util import get_indicator_adapter
import six


DOMAIN = 'icds-cas'
DATA_SOURCE_NAME = 'static-icds-cas-static-person_cases_v2'


STATE_IDS = [
    'f98e91aa003accb7b849a0f18ebd7039',
    'f9b47ea2ee2d8a02acddeeb491d3e175',
    'a2fcb186e9be8464e167bb1c56ce8fd9',
    'f1cd643f0df908421abd915298ba57bc',
    'd982a6fb4cca0824fbde59db18d3800f',
    '9cd4fd88d9f047088a377b7e7d144830',
    'ea4d587fa93a2ed8300853d51db661ef',
]


def create_async_indicator(doc_id):
    assert isinstance(doc_id, six.text_type)
    return AsyncIndicator(
        doc_id=doc_id, doc_type="CommCareCase", domain=DOMAIN,
        indicator_config_ids=[DATA_SOURCE_NAME]
    )


class Command(BaseCommand):
    help = ""

    def handle(self, *args, **options):
        data_source, is_static = get_datasource_config(DATA_SOURCE_NAME, DOMAIN)
        assert is_static
        adapter = get_indicator_adapter(data_source)
        table = adapter.get_table()
        for state_id in STATE_IDS:
            null_query = adapter.session_helper.Session.query(table.columns.doc_id)
            null_query = null_query.filter(
                table.columns.state_id == state_id,
                table.columns.aadhar_date == None
            ).all()

            AsyncIndicator.objects.bulk_create([
                create_async_indicator(doc_id[0])
                for doc_id in null_query
            ], batch_size=500)
