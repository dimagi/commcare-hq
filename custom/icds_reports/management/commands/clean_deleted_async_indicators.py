import logging
from collections import defaultdict

from django.core.management.base import BaseCommand

from pillowtop.feed.interface import ChangeMeta

from corehq.apps.change_feed import data_sources, topics
from corehq.apps.change_feed.producer import producer
from corehq.apps.userreports.models import (
    AsyncIndicator,
    StaticDataSourceConfiguration,
)
from corehq.apps.userreports.util import get_indicator_adapter
from corehq.util.argparse_types import date_type

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = """
    """

    def add_arguments(self, parser):
        parser.add_argument(dest='start_date', type=date_type)
        parser.add_argument(dest='end_date', type=date_type)
        parser.add_argument('--execute', action='store_true')

    def handle(self, start_date, end_date, execute, **options):
        config_ids = (
            'static-ccs_record_cases_monthly_v2',
            'static-child_cases_monthly_v2'
        )
        for config_id in config_ids:
            self.process(config_id, start_date, end_date, execute)

    def process(self, config_id, start_date, end_date, execute):
        indicators = AsyncIndicator.objects.filter(
            indicator_config_ids=[config_id],
            date_created__gte=start_date, date_created__lt=end_date,
        ).all()

        datasource_id = StaticDataSourceConfiguration.get_doc_id('icds-cas', config_id)
        data_source = StaticDataSourceConfiguration.by_id(datasource_id)
        doc_store = data_sources.get_document_store_for_doc_type(
            'icds-cas', 'CommCareCase', load_source="clean_deleted_async_indicators",
        )
        doc_ids = [indicator.doc_id for indicator in indicators]
        doc_ids_to_delete = [
            doc['id']
            for doc in doc_store.iter_documents(doc_ids)
            if not data_source.filter(doc)
        ]

        if doc_ids_to_delete:
            logger.info("Found following doc_ids to delete:")
            for doc_id in doc_ids_to_delete:
                logger.info(doc_id)

        if doc_ids_to_delete and execute:
            adapter = get_indicator_adapter(data_source)
            logger.info("Deleting from UCR table")
            adapter.bulk_delete({{'_id': doc_id for doc_id in doc_ids_to_delete}})
            # if everything went well, delete the records
            logger.info("Deleting from async indicator table")
            AsyncIndicator.objects.filter(doc_id__in=doc_ids_to_delete).delete()
