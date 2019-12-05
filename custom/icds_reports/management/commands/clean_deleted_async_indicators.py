import logging

from django.core.management.base import BaseCommand

from corehq.apps.change_feed import data_sources
from corehq.apps.userreports.models import (
    AsyncIndicator,
    StaticDataSourceConfiguration,
)
from corehq.apps.userreports.specs import EvaluationContext
from corehq.apps.userreports.util import get_indicator_adapter
from corehq.util.argparse_types import utc_timestamp

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = """
    """

    def add_arguments(self, parser):
        parser.add_argument(dest='start_date', type=utc_timestamp)
        parser.add_argument(dest='end_date', type=utc_timestamp)
        parser.add_argument('--execute', action='store_true')

    def handle(self, start_date, end_date, execute, **options):
        config_ids = (
            'static-ccs_record_cases_monthly_v2',
            'static-child_cases_monthly_v2'
        )
        for config_id in config_ids:
            self.process(config_id, start_date, end_date, execute)

    def process(self, config_id, start_date, end_date, execute):
        datasource_id = StaticDataSourceConfiguration.get_doc_id('icds-cas', config_id)
        indicators = AsyncIndicator.objects.filter(
            indicator_config_ids=[datasource_id],
            date_created__gte=start_date, date_created__lt=end_date,
        ).all()

        data_source = StaticDataSourceConfiguration.by_id(datasource_id)
        doc_store = data_sources.get_document_store_for_doc_type(
            'icds-cas', 'CommCareCase', load_source="clean_deleted_async_indicators",
        )
        doc_ids = [indicator.doc_id for indicator in indicators]
        doc_ids_to_delete = [
            doc['_id']
            for doc in doc_store.iter_documents(doc_ids)
            if not data_source.filter(doc) or not data_source.parsed_expression(doc, EvaluationContext(doc))
        ]

        if doc_ids_to_delete:
            logger.info("Found following doc_ids to delete:")
            with open(f'{config_id}_doc_ids_deleted.csv', 'w', newline='') as csvfile:
                for doc_id in doc_ids_to_delete:
                    csvfile.write(doc_id)

        if doc_ids_to_delete and execute:
            adapter = get_indicator_adapter(data_source)
            logger.info("Deleting from UCR table")
            adapter.bulk_delete({{'_id': doc_id for doc_id in doc_ids_to_delete}})
            # if everything went well, delete the records
            logger.info("Deleting from async indicator table")
            AsyncIndicator.objects.filter(doc_id__in=doc_ids_to_delete).delete()
