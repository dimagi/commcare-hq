from django.conf import settings
from kafka import KafkaConsumer
from casexml.apps.case.models import CommCareCase
from corehq.apps.change_feed import topics, change_feed_logger
from corehq.apps.change_feed.consumer.feed import KafkaChangeFeed
from pillowtop.checkpoints.manager import PillowCheckpoint
from pillowtop.dao.couch import CouchDocumentStore
from pillowtop.pillow.interface import ConstructedPillow
from pillowtop.processor import LoggingProcessor


def get_case_consumer_pillow():
    document_store = CouchDocumentStore(CommCareCase.get_db())
    checkpoint = PillowCheckpoint(
        document_store,
        'kafka-case-pillow-checkpoint',
    )
    return ConstructedPillow(
        document_store=document_store,
        checkpoint=checkpoint,
        change_feed=KafkaChangeFeed(topics.CASE),
        processor=LoggingProcessor(logger=change_feed_logger),
    )


