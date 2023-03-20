from collections import namedtuple
from functools import lru_cache

from pillowtop.checkpoints.manager import (
    get_checkpoint_for_elasticsearch_pillow,
)
from pillowtop.pillow.interface import ConstructedPillow
from pillowtop.processors import PillowProcessor

from corehq.apps.change_feed import topics
from corehq.apps.change_feed.consumer.feed import (
    KafkaChangeFeed,
    KafkaCheckpointEventHandler,
)
from corehq.apps.export.models.new import LedgerSectionEntry
from corehq.apps.locations.models import SQLLocation
from corehq.util.quickcache import quickcache


@quickcache(['case_id'])
def _location_id_for_case(case_id):
    try:
        return SQLLocation.objects.get(supply_point_id=case_id).location_id
    except SQLLocation.DoesNotExist:
        return None


def _get_daily_consumption_for_ledger(ledger):
    from corehq.apps.commtrack.consumption import get_consumption_for_ledger_json
    daily_consumption = get_consumption_for_ledger_json(ledger)
    from corehq.form_processor.backends.sql.dbaccessors import LedgerAccessorSQL
    ledger_value = LedgerAccessorSQL.get_ledger_value(
        ledger['case_id'], ledger['section_id'], ledger['entry_id']
    )
    ledger_value.daily_consumption = daily_consumption
    LedgerAccessorSQL.save_ledger_values([ledger_value])
    return daily_consumption


def _update_ledger_section_entry_combinations(ledger):
    current_combos = _get_ledger_section_combinations(ledger['domain'])
    if (ledger['section_id'], ledger['entry_id']) in current_combos:
        return

    # use get_or_create because this may be created by another parallel process
    LedgerSectionEntry.objects.get_or_create(
        domain=ledger['domain'],
        section_id=ledger['section_id'],
        entry_id=ledger['entry_id'],
    )

    # clear the lru_cache so that next time a ledger is saved, we get the combinations
    _get_ledger_section_combinations.cache_clear()


@lru_cache()
def _get_ledger_section_combinations(domain):
    return list(LedgerSectionEntry.objects.filter(domain=domain).values_list('section_id', 'entry_id').all())


class LedgerProcessor(PillowProcessor):
    """Updates ledger section and entry combinations (exports), daily consumption and case location ids

    Reads from:
      - Kafka topics: ledger
      - Ledger data source

    Writes to:
      - LedgerSectionEntry postgres table
      - Ledger data source
    """

    def process_change(self, change):
        if change.deleted:
            return

        ledger = change.get_document()
        from corehq.apps.commtrack.models import CommtrackConfig
        commtrack_config = CommtrackConfig.for_domain(ledger['domain'])

        if commtrack_config and commtrack_config.use_auto_consumption:
            daily_consumption = _get_daily_consumption_for_ledger(ledger)
            ledger['daily_consumption'] = daily_consumption

        if not ledger.get('location_id') and ledger.get('case_id'):
            ledger['location_id'] = _location_id_for_case(ledger['case_id'])

        _update_ledger_section_entry_combinations(ledger)


def get_ledger_to_elasticsearch_pillow(pillow_id='LedgerToElasticsearchPillow', num_processes=1,
                                       process_num=0, **kwargs):
    """Ledger pillow

    Note that this pillow's id references Elasticsearch, but it no longer saves to ES.
    It has been kept to keep the checkpoint consistent, and can be changed at any time.

    Processors:
      - :py:class:`corehq.pillows.ledger.LedgerProcessor`
    """
    assert pillow_id == 'LedgerToElasticsearchPillow', 'Pillow ID is not allowed to change'
    index_name = "ledgers_2016-03-15"
    checkpoint = get_checkpoint_for_elasticsearch_pillow(
        pillow_id, index_name, [topics.LEDGER]
    )
    change_feed = KafkaChangeFeed(
        topics=[topics.LEDGER], client_id='ledgers-to-es', num_processes=num_processes, process_num=process_num
    )
    return ConstructedPillow(
        name=pillow_id,
        checkpoint=checkpoint,
        change_feed=change_feed,
        processor=LedgerProcessor(),
        change_processed_event_handler=KafkaCheckpointEventHandler(
            checkpoint=checkpoint, checkpoint_frequency=100, change_feed=change_feed
        ),
    )
