import logging
from collections import defaultdict

from django.core.management.base import BaseCommand

from pillowtop.feed.interface import ChangeMeta

from corehq.apps.change_feed import data_sources, topics
from corehq.apps.change_feed.producer import producer
from corehq.apps.userreports.models import AsyncIndicator
from corehq.util.argparse_types import date_type

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = """
    """

    def add_arguments(self, parser):
        parser.add_argument(
            dest='cleanup_date',
            type=date_type,
            help="The date before which to send the indicators through kafka",
        )

    def handle(self, cleanup_date, **options):
        indicators = AsyncIndicator.objects.filter(date_created__lt=cleanup_date).all()
        indicators_by_domain_doc_type = defaultdict(list)
        for indicator in indicators:
            indicators_by_domain_doc_type[(indicator.domain, indicator.doc_type)].append(indicator)

        for domain_doc_type, indicators in indicators_by_domain_doc_type.values():
            doc_store = data_sources.get_document_store_for_doc_type(
                domain_doc_type[0], domain_doc_type[1], load_source="clean_async_indicators",
            )
            doc_ids = [indicator.doc_id for indicator in indicators]

            for doc in doc_store.iter_documents(doc_ids):
                doc_id = doc['_id']
                if domain_doc_type[0] == 'XFormInstance':
                    producer.send_change(
                        topics.FORM_SQL,
                        ChangeMeta(
                            document_id=doc_id,
                            data_source_type=data_sources.SOURCE_SQL,
                            data_source_name=data_sources.FORM_SQL,
                            document_type='XFormInstance',
                            document_subtype=doc['xmlns'],
                            domain=doc['domain'],
                            is_deletion=False,
                        )
                    )
                    logging.info(f"XForm {doc_id} sent through kafka")
                elif domain_doc_type[0] == 'CommCareCase':
                    producer.send_change(
                        topics.CASE_SQL,
                        ChangeMeta(
                            document_id=doc_id,
                            data_source_type=data_sources.SOURCE_SQL,
                            data_source_name=data_sources.CASE_SQL,
                            document_type='CommCareCase',
                            document_subtype=doc['type'],
                            domain=doc['domain'],
                            is_deletion=False,
                        )
                    )
                    logging.info(f"Case {doc_id} sent through kafka")

        # if everything went well, delete the records
        AsyncIndicator.objects.filter(date_created__lt=cleanup_date).delete()
