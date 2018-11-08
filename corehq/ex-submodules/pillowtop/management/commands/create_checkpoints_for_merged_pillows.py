from __future__ import print_function

from __future__ import absolute_import
from __future__ import unicode_literals
from django.core.management.base import BaseCommand
from django.db.models import Min

from pillowtop.models import KafkaCheckpoint
from pillowtop.exceptions import PillowNotFoundError
from pillowtop.utils import get_pillow_by_name


PILLOW_REORG_MAPPING = {
    'kafka-case-ucr-es': [
        'kafka-ucr-main',
        'kafka-ucr-static',
        'ReportCaseToElasticsearchPillow',
        'CaseToElasticsearchPillow'
    ],
    'kafka-xform-ucr-es': [
        'kafka-ucr-main',
        'kafka-ucr-static',
        'ReportXFormToElasticsearchPillow',
        'XFormToElasticsearchPillow',
        'FormSubmissionMetadataTrackerProcessor',
        'unknown-users-pillow'
    ],
    'GroupESPillow': [
        'GroupPillow',
        'GroupToUserPillow'
    ],
    'user-to-es-ucr-pillow': [
        'kafka-ucr-main',
        'kafka-ucr-static',
        'UserPillow'
    ]
}


def pillow_to_checkpoint_id_mapping():
    checkpoint_mapping = {}

    for new_pillow_name, old_pillows in PILLOW_REORG_MAPPING.iteritems():
        new_pillow = get_pillow_by_name(new_pillow_name)
        checkpoint_mapping[new_pillow.checkpoint.checkpoint_id] = []
        checkpoints = []
        for pillow_name in old_pillows:
            old_pillow = get_pillow_by_name(pillow_name)
            checkpoints.append(old_pillow.checkpoint.checkpoint_id)
        checkpoint_mapping[new_pillow.checkpoint.checkpoint_id] = checkpoints

    new_checkpoints = KafkaCheckpoint.objects.filter(checkpoint_id__in=checkpoint_mapping.keys())
    assert len(new_checkpoints) == 0, "Checkpoints already exist for merged pillows!"
    return checkpoint_mapping


class Command(BaseCommand):
    """
    One off command to create checkpoints and set offsets for merged pillows
    All the to be merged pillows must be stopped, before running this command

    This creates checkpoints for all the new pillows that are merge
        of old pillows according to PILLOW_REORG_MAPPING. The offsets for
        merged pillow checkpoints will be set to oldest offsets of all
        checkpoints of merged pillows per respective topic and partition
        of each checkpoint. This ensures that all changes are processed by
        merged pillow at the expense of partially reprocessing some.
    """

    help = "Create checkpoints for merged pillows"

    def add_arguments(self, parser):
        parser.add_argument(
            '--check',
            action='store_true',
            dest='check',
            default=False,
            help="Just print the summary of changes",
        )

    def handle(self, **options):
        check = options['check']
        confirm = input(
            """
            Please make sure you have read <TODO; add process README>.
            Have you stopped all the to be merged pillows and added new pillows
            to this environment's app-processes.yml? y/N?
            """
        )

        if confirm != 'y':
            print("Checkpoint creation cancelled")
            return

        try:
            checkpoint_id_mapping = pillow_to_checkpoint_id_mapping()
        except PillowNotFoundError as e:
            print(e)
            print("Please make sure that pillows are defined in current release")
            return

        new_objects = []
        for new_checkpoint_id, old_checkpoint_ids in checkpoint_id_mapping.iteritems():
            old_checkpoints = KafkaCheckpoint.objects.filter(checkpoint_id__in=old_checkpoint_ids)
            topic_partitions = old_checkpoints.values('topic', 'partition').distinct()
            for result in topic_partitions:
                topic = result['topic']
                partition = result['partition']
                min_offset = old_checkpoints.filter(
                    topic=topic, parition=partition).annotate(Min('offset')))
                params = {
                    'checkpoint_id': new_checkpoint_id,
                    'topic': topic,
                    'partition': partition,
                    'offset': min_offset
                }
                if check:
                    print("Checkpoint to be created")
                else:
                    print("Creating checkpoint")
                    KafkaCheckpoint.objects.get_or_create(
                        **params
                    )
                print("""
                    id: {checkpoint_id},
                    topic: {topic},
                    partition: {partition},
                    offset: {offset}
                """.format(**params))

