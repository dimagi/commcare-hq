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
    daily_consumption = _get_consumption_for_ledger(ledger)
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


def _get_consumption_for_ledger(ledger):
    from corehq.apps.domain.models import Domain
    from casexml.apps.stock.consumption import compute_daily_consumption
    from dimagi.utils.parsing import string_to_utc_datetime

    domain_name = ledger['domain']
    domain = Domain.get_by_name(domain_name)
    if domain and domain.commtrack_settings:
        consumption_calc = domain.commtrack_settings.get_consumption_config()
    else:
        consumption_calc = None
    daily_consumption = compute_daily_consumption(
        domain_name,
        ledger['case_id'],
        ledger['entry_id'],
        string_to_utc_datetime(ledger['last_modified']),
        'stock',
        consumption_calc
    )
    return daily_consumption


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
