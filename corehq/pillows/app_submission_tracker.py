from corehq.apps.change_feed import topics
from corehq.apps.change_feed.consumer.feed import KafkaChangeFeed, MultiTopicCheckpointEventHandler
from pillowtop.checkpoints.manager import PillowCheckpoint
from pillowtop.pillow.interface import ConstructedPillow
from pillowtop.processors.form import AppFormSubmissionTrackerProcessor


def get_app_form_submission_tracker_pillow(pillow_id='AppFormSubmissionTrackerPillow'):
    """
    This gets a pillow which iterates through all forms and marks the corresponding app
    as having submissions. This could be expanded to be more generic and include
    other processing that needs to happen on each form
    """
    checkpoint = PillowCheckpoint('app-form-submission-tracker')
    form_processor = AppFormSubmissionTrackerProcessor()
    change_feed = KafkaChangeFeed(topics=[topics.FORM, topics.FORM_SQL], group_id='form-processsor')
    return ConstructedPillow(
        name=pillow_id,
        checkpoint=checkpoint,
        change_feed=change_feed,
        processor=form_processor,
        change_processed_event_handler=MultiTopicCheckpointEventHandler(
            checkpoint=checkpoint, checkpoint_frequency=100, change_feed=change_feed,
        ),
    )
