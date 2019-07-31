from corehq.apps.change_feed.consumer.feed import KafkaChangeFeed, KafkaCheckpointEventHandler
from corehq.apps.change_feed.topics import CASE_TOPICS
from corehq.messaging.tasks import update_messaging_for_case
from pillowtop.checkpoints.manager import KafkaPillowCheckpoint
from pillowtop.const import DEFAULT_PROCESSOR_CHUNK_SIZE
from pillowtop.pillow.interface import ConstructedPillow
from pillowtop.processors import BulkPillowProcessor


class CaseMessagingSyncProcessor(BulkPillowProcessor):
    def process_change(self, change):
        update_messaging_for_case(
            change.metadata.domain,
            change.id,
            change.get_document(),
        )

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
