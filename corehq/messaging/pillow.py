from datetime import datetime

import attr

from corehq.apps.change_feed.consumer.feed import KafkaChangeFeed, KafkaCheckpointEventHandler
from corehq.apps.change_feed.topics import CASE_TOPICS
from corehq.apps.data_interfaces.models import AutomaticUpdateRule
from corehq.messaging.tasks import update_messaging_for_case
from pillowtop.checkpoints.manager import KafkaPillowCheckpoint
from pillowtop.const import DEFAULT_PROCESSOR_CHUNK_SIZE
from pillowtop.pillow.interface import ConstructedPillow
from pillowtop.processors import BulkPillowProcessor


@attr.s
class CaseRules(object):
    date_loaded = attr.ib()
    by_case_type = attr.ib()

    def expired(self):
        return (datetime.utcnow() - self.date_loaded) > 30 * 60


class CaseMessagingSyncProcessor(BulkPillowProcessor):
    def __init__(self):
        self.rules_by_domain = {}

    def _get_rules(self, domain, case_type):
        domain_rules = self.rules_by_domain.get(domain)
        if not domain_rules or domain_rules.expired():
            rules = AutomaticUpdateRule.by_domain_cached(domain, AutomaticUpdateRule.WORKFLOW_SCHEDULING)
            domain_rules = CaseRules(
                datetime.utcnow(), AutomaticUpdateRule.organize_rules_by_case_type(rules)
            )
            self.rules_by_domain[domain] = domain_rules
        return domain_rules.by_case_type.get(case_type, [])

    def process_change(self, change):
        case = change.get_document()
        update_messaging_for_case(
            change.metadata.domain,
            change.id,
            case,
        )
        if case and not case.is_deleted:
            rules = self._get_rules(change.metadata.domain, case.type)
            for rule in rules:
                rule.run_rule(case, datetime.utcnow())

    def process_changes_chunk(self, changes_chunk):
        errors = []
        for change in changes_chunk:
            try:
                self.process_change(change)
            except Exception as e:
                errors.append((change, e))
        return [], errors


def get_case_messaging_sync_pillow(pillow_id='case_messaging_sync_pillow', topics=None,
                         num_processes=1, process_num=0,
                         processor_chunk_size=DEFAULT_PROCESSOR_CHUNK_SIZE, **kwargs):
    if topics:
        assert set(topics).issubset(CASE_TOPICS), "This is a pillow to process cases only"
    topics = topics or CASE_TOPICS
    change_feed = KafkaChangeFeed(
        topics, client_id=pillow_id, num_processes=num_processes, process_num=process_num
    )
    checkpoint = KafkaPillowCheckpoint(pillow_id, topics)
    event_handler = KafkaCheckpointEventHandler(
        checkpoint=checkpoint, checkpoint_frequency=1000, change_feed=change_feed,
    )
    return ConstructedPillow(
        name=pillow_id,
        change_feed=change_feed,
        checkpoint=checkpoint,
        change_processed_event_handler=event_handler,
        processor=[CaseMessagingSyncProcessor()],
        processor_chunk_size=processor_chunk_size
    )
