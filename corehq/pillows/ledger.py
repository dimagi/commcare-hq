from corehq.apps.change_feed import topics
from corehq.apps.change_feed.consumer.feed import KafkaChangeFeed
from corehq.elastic import get_es_new
from corehq.form_processor.change_providers import (
    LedgerV2ChangeProvider, DjangoModelChangeProvider, _ledger_v1_to_change
)
from corehq.form_processor.utils.general import should_use_sql_backend
from corehq.pillows.mappings.ledger_mapping import LEDGER_INDEX_INFO
from pillowtop.checkpoints.manager import PillowCheckpoint, PillowCheckpointEventHandler
from pillowtop.pillow.interface import ConstructedPillow
from pillowtop.processors.elastic import ElasticProcessor
from pillowtop.reindexer.reindexer import ElasticPillowReindexer


def _set_ledger_consumption(ledger):
    from corehq.apps.commtrack.consumption import get_consumption_for_ledger_json
    daily_consumption = get_consumption_for_ledger_json(ledger)
    if should_use_sql_backend(ledger['domain']):
        from corehq.form_processor.backends.sql.dbaccessors import LedgerAccessorSQL
        ledger_value = LedgerAccessorSQL.get_ledger_value(
            ledger['case_id'], ledger['section_id'], ledger['entry_id']
        )
        ledger_value.daily_consumption = daily_consumption
        LedgerAccessorSQL.save_ledger_values([ledger_value])
    else:
        from corehq.apps.commtrack.models import StockState
        StockState.objects.filter(pk=ledger['_id']).update(daily_consumption=daily_consumption)

    ledger['daily_consumption'] = daily_consumption
    return ledger


def get_ledger_to_elasticsearch_pillow(pillow_id='LedgerToElasticsearchPillow'):
    checkpoint = PillowCheckpoint(
        'ledger-to-elasticsearch',
    )
    processor = ElasticProcessor(
        elasticsearch=get_es_new(),
        index_info=LEDGER_INDEX_INFO,
        doc_prep_fn=_set_ledger_consumption
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


def get_ledger_v1_reindexer():
    from corehq.apps.commtrack.models import StockState
    return ElasticPillowReindexer(
        pillow=get_ledger_to_elasticsearch_pillow(),
        change_provider=DjangoModelChangeProvider(StockState, _ledger_v1_to_change),
        elasticsearch=get_es_new(),
        index_info=LEDGER_INDEX_INFO,
    )
