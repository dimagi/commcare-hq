from __future__ import absolute_import
from __future__ import unicode_literals
from corehq.apps.change_feed import topics
from corehq.apps.change_feed.consumer.feed import KafkaChangeFeed, KafkaCheckpointEventHandler
from corehq.apps.locations.models import SQLLocation
from corehq.elastic import get_es_new
from corehq.form_processor.backends.sql.dbaccessors import LedgerReindexAccessor
from corehq.form_processor.change_publishers import change_meta_from_ledger_v1
from corehq.form_processor.utils.general import should_use_sql_backend
from corehq.pillows.mappings.ledger_mapping import LEDGER_INDEX_INFO
from corehq.util.doc_processor.sql import SqlDocumentProvider
from corehq.util.quickcache import quickcache
from pillowtop.checkpoints.manager import get_checkpoint_for_elasticsearch_pillow
from pillowtop.feed.interface import Change
from pillowtop.pillow.interface import ConstructedPillow
from pillowtop.processors.elastic import ElasticProcessor
from pillowtop.reindexer.change_providers.django_model import DjangoModelChangeProvider
from pillowtop.reindexer.reindexer import (
    ElasticPillowReindexer, ResumableBulkElasticPillowReindexer, ReindexerFactory
)


@quickcache(['case_id'])
def _location_id_for_case(case_id):
    try:
        return SQLLocation.objects.get(supply_point_id=case_id).location_id
    except SQLLocation.DoesNotExist:
        return None


def _prepare_ledger_for_es(ledger):
    from corehq.apps.commtrack.models import CommtrackConfig
    commtrack_config = CommtrackConfig.for_domain(ledger['domain'])

    if commtrack_config and commtrack_config.use_auto_consumption:
        daily_consumption = _get_daily_consumption_for_ledger(ledger)
        ledger['daily_consumption'] = daily_consumption

    if not ledger.get('location_id') and ledger.get('case_id'):
        ledger['location_id'] = _location_id_for_case(ledger['case_id'])

    return ledger


def _get_daily_consumption_for_ledger(ledger):
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

    return daily_consumption


def get_ledger_to_elasticsearch_pillow(pillow_id='LedgerToElasticsearchPillow', num_processes=1,
                                       process_num=0, **kwargs):
    assert pillow_id == 'LedgerToElasticsearchPillow', 'Pillow ID is not allowed to change'
    checkpoint = get_checkpoint_for_elasticsearch_pillow(pillow_id, LEDGER_INDEX_INFO, [topics.LEDGER])
    processor = ElasticProcessor(
        elasticsearch=get_es_new(),
        index_info=LEDGER_INDEX_INFO,
        doc_prep_fn=_prepare_ledger_for_es
    )
    change_feed = KafkaChangeFeed(
        topics=[topics.LEDGER], group_id='ledgers-to-es', num_processes=num_processes, process_num=process_num
    )
    return ConstructedPillow(
        name=pillow_id,
        checkpoint=checkpoint,
        change_feed=change_feed,
        processor=processor,
        change_processed_event_handler=KafkaCheckpointEventHandler(
            checkpoint=checkpoint, checkpoint_frequency=100, change_feed=change_feed
        ),
    )


class LedgerV2ReindexerFactory(ReindexerFactory):
    slug = 'ledger-v2'
    arg_contributors = [
        ReindexerFactory.resumable_reindexer_args,
        ReindexerFactory.elastic_reindexer_args,
        ReindexerFactory.domain_arg,
    ]

    def build(self):
        domain = self.options.pop('domain', None)
        iteration_key = "SqlCaseToElasticsearchPillow_{}_reindexer_{}".format(
            LEDGER_INDEX_INFO.index, domain or 'all'
        )
        doc_provider = SqlDocumentProvider(iteration_key, LedgerReindexAccessor(domain=domain))
        return ResumableBulkElasticPillowReindexer(
            doc_provider,
            elasticsearch=get_es_new(),
            index_info=LEDGER_INDEX_INFO,
            doc_transform=_prepare_ledger_for_es,
            **self.options
        )


class LedgerV1ReindexerFactory(ReindexerFactory):
    slug = 'ledger-v1'
    arg_contributors = [
        ReindexerFactory.elastic_reindexer_args,
    ]

    def build(self):
        from corehq.apps.commtrack.models import StockState
        return ElasticPillowReindexer(
            pillow=get_ledger_to_elasticsearch_pillow(),
            change_provider=DjangoModelChangeProvider(StockState, _ledger_v1_to_change),
            elasticsearch=get_es_new(),
            index_info=LEDGER_INDEX_INFO,
            **self.options
        )


def _ledger_v1_to_change(stock_state):
    return Change(
        id=stock_state.pk,
        sequence_id=None,
        document=stock_state.to_json(),
        deleted=False,
        metadata=change_meta_from_ledger_v1(stock_state),
        document_store=None,
    )
