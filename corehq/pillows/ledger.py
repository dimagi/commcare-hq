from corehq.apps.change_feed import topics
from corehq.apps.change_feed.consumer.feed import KafkaChangeFeed
from corehq.elastic import get_es_new
from corehq.form_processor.change_providers import (
    LedgerV2ChangeProvider, DjangoModelChangeProvider, _stock_state_to_change
)
from corehq.pillows.mappings.ledger_mapping import LEDGER_INDEX_INFO
from pillowtop.checkpoints.manager import PillowCheckpoint, PillowCheckpointEventHandler
from pillowtop.pillow.interface import ConstructedPillow
from pillowtop.processors.elastic import ElasticProcessor
from pillowtop.reindexer.reindexer import ElasticPillowReindexer


def get_ledger_to_elasticsearch_pillow(pillow_id='LedgerToElasticsearchPillow'):
    checkpoint = PillowCheckpoint(
        'ledger-to-elasticsearch',
    )
    processor = ElasticProcessor(
        elasticsearch=get_es_new(),
        index_info=LEDGER_INDEX_INFO
    )
    return ConstructedPillow(
        name=pillow_id,
        checkpoint=checkpoint,
        change_feed=KafkaChangeFeed(topics=[topics.LEDGER], group_id='ledgers-to-es'),
        processor=processor,
        change_processed_event_handler=PillowCheckpointEventHandler(
            checkpoint=checkpoint, checkpoint_frequency=100
        ),
    )


def get_ledger_v2_reindexer():
    return ElasticPillowReindexer(
        pillow=get_ledger_to_elasticsearch_pillow(),
        change_provider=LedgerV2ChangeProvider(),
        elasticsearch=get_es_new(),
        index_info=LEDGER_INDEX_INFO,
    )


def get_stock_state_reindexer():
    from corehq.apps.commtrack.models import StockState
    return ElasticPillowReindexer(
        pillow=get_ledger_to_elasticsearch_pillow(),
        change_provider=DjangoModelChangeProvider(StockState, _stock_state_to_change),
        elasticsearch=get_es_new(),
        index_info=LEDGER_INDEX_INFO,
    )
