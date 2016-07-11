import json
from collections import namedtuple

from django.conf import settings
from casexml.apps.case.models import CommCareCase
import logging

from corehq.apps.change_feed import topics
from pillowtop.checkpoints.manager import DEFAULT_EMPTY_CHECKPOINT_SEQUENCE
from pillowtop.checkpoints.util import construct_checkpoint_doc_id_from_name
from pillowtop.utils import get_pillow_config_by_name


def noop_reverse_migration(apps, schema_editor):
    # by default the reverse migration does nothing
    pass


def migrate_legacy_pillows(migration_apps, pillow_names):
    for pillow_name in pillow_names:
        migrate_legacy_pillow_by_name(migration_apps, pillow_name)


def migrate_legacy_pillow_by_name(migration_apps, pillow_name):
    if settings.UNIT_TESTING:
        return
    try:
        DjangoPillowCheckpoint = migration_apps.get_model('pillowtop', 'DjangoPillowCheckpoint')
        pillow_config = get_pillow_config_by_name(pillow_name)
        checkpoint_id = construct_checkpoint_doc_id_from_name(pillow_config.get_class().get_legacy_name())
        legacy_checkpoint = CommCareCase.get_db().get(checkpoint_id)
        new_checkpoint = DjangoPillowCheckpoint(
            checkpoint_id=pillow_config.get_instance().checkpoint.checkpoint_id,
            sequence=legacy_checkpoint['seq'],
            old_sequence=legacy_checkpoint.get('old_seq', None)
        )
        new_checkpoint.save()
    except Exception as e:
        logging.exception('Failed to update pillow checkpoint. {}'.format(e))


CheckpointTopic = namedtuple("CheckpointTopic", "checkpoint_id, topic")


def merge_kafka_pillow_checkpoints(new_checkpoint_id, checkpoint_topics, migration_apps):
    if settings.UNIT_TESTING:
        return
    try:
        DjangoPillowCheckpoint = migration_apps.get_model('pillowtop', 'DjangoPillowCheckpoint')

        checkpoint_doc_topics = []
        for checkpoint_id, topic in checkpoint_topics:
            try:
                checkpoint_doc = DjangoPillowCheckpoint.objects.get(checkpoint_id=checkpoint_id)
            except DjangoPillowCheckpoint.DoesNotExist:
                logging.warning('Checkpoint not found: {}'.format(checkpoint_id))
                continue

            if topic:
                assert topic in topics.ALL, "Unknown topic: {}".format(topic)

            checkpoint_doc_topics.append((checkpoint_doc, topic))

        merged_sequence = get_merged_sequence(checkpoint_doc_topics)

        new_checkpoint = DjangoPillowCheckpoint(
            checkpoint_id=new_checkpoint_id,
            sequence=json.dumps(merged_sequence),
            sequence_format='json'
        )
        new_checkpoint.save()
    except Exception as e:
        logging.exception('Failed to merge pillow checkpoints: {}. {}'.format(new_checkpoint_id, e))


def get_merged_sequence(checkpoints_topics):
    merged_sequence = {}

    def _merge_seq(topic, seq):
        existing_seq = merged_sequence.get(topic, None)
        merged_sequence[topic] = min(seq, existing_seq) if existing_seq is not None else seq

    for checkpoint_doc, topic in checkpoints_topics:
        if checkpoint_doc.sequence == DEFAULT_EMPTY_CHECKPOINT_SEQUENCE:
            continue

        if checkpoint_doc.sequence_format != 'json':
            _merge_seq(topic, int(checkpoint_doc.sequence))
        else:
            sequence = json.loads(checkpoint_doc.sequence)
            for sub_topic, seq in sequence.items():
                _merge_seq(sub_topic, seq)
    return merged_sequence
