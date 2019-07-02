from __future__ import print_function
from __future__ import absolute_import
from __future__ import unicode_literals

import six
from django.core.management.base import BaseCommand
from django.db.models import Min
from six.moves import input

from pillowtop.models import KafkaCheckpoint
from pillowtop.exceptions import PillowNotFoundError
from pillowtop.utils import get_pillow_by_name


PILLOW_REORG_MAPPING = {
    'case-pillow': [
        'kafka-ucr-main',
        'kafka-ucr-static',
        'ReportCaseToElasticsearchPillow',
        'CaseToElasticsearchPillow'
    ],
    'xform-pillow': [
        'kafka-ucr-main',
        'kafka-ucr-static',
        'ReportXFormToElasticsearchPillow',
        'XFormToElasticsearchPillow',
        'FormSubmissionMetadataTrackerPillow',
        'UnknownUsersPillow'
    ],
    'group-pillow': [
        'GroupPillow',
        'GroupToUserPillow'
    ],
    'user-pillow': [
        'kafka-ucr-main',
        'kafka-ucr-static',
        'UserPillow'
    ]
}


def pillow_to_checkpoint_id_mapping():
    checkpoint_mapping = {}

    for new_pillow_name, old_pillows in six.iteritems(PILLOW_REORG_MAPPING):
        new_pillow = get_pillow_by_name(new_pillow_name)
        checkpoint_mapping[new_pillow.checkpoint.checkpoint_id] = []
        checkpoints = []
        for pillow_name in old_pillows:
            old_pillow = get_pillow_by_name(pillow_name)
            checkpoints.append(old_pillow.checkpoint.checkpoint_id)
        checkpoint_mapping[new_pillow.checkpoint.checkpoint_id] = checkpoints, list(new_pillow.topics)

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
            '--cleanup-first',
            action='store_true',
            dest='cleanup',
            default=False,
            help="Delete new checkpoints before recreating them [useful if it fails midway]"
        )

    def handle(self, **options):
        confirm = input(
            """
            Please make sure you have read https://dimagi.github.io/commcare-cloud/changelog/0007-reorganize-pillows.html.

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

        new_checkpoints = KafkaCheckpoint.objects.filter(checkpoint_id__in=checkpoint_id_mapping)
        if options['cleanup']:
            new_checkpoints.delete()

        self._create_checkpoints(checkpoint_id_mapping, False)
        confirm = input(
            """
            Please check above reset offsets and make sure all merged checkpoints are relatively close.

            Do you want to proceed resetting per the above output? y/N?
            """
        )
        if confirm != 'y':
            print("Checkpoint creation cancelled")
            return
        else:
            self._create_checkpoints(checkpoint_id_mapping, True)

    def _create_checkpoints(self, checkpoint_id_mapping, skip_check):
        for new_checkpoint_id, (old_checkpoint_ids, new_topics) in six.iteritems(checkpoint_id_mapping):
            print("\nCalculating checkpoints for {}\n".format(new_checkpoint_id))
            old_checkpoints = KafkaCheckpoint.objects.filter(checkpoint_id__in=old_checkpoint_ids, topic__in=new_topics)
            topic_partitions = old_checkpoints.values('topic', 'partition').distinct()
            print("\t### Current checkpoints ###")
            print("\tcheckpoint, topic, partition, offset")
            for checkpoint in old_checkpoints.order_by('topic', 'partition'):
                print("\t{}, {}, {}, {}".format(
                    checkpoint.checkpoint_id,
                    checkpoint.topic,
                    checkpoint.partition,
                    checkpoint.offset))
            msg = "Creating checkpoints for" if skip_check else "Checkpoints to be created for"
            print("\n\t### {} - {} ###".format(msg, new_checkpoint_id))
            print("\ttopic, partition, offset")
            for result in topic_partitions:
                topic = result['topic']
                partition = result['partition']
                min_offset = old_checkpoints.filter(
                    topic=topic, partition=partition).aggregate(Min('offset'))['offset__min']
                if skip_check:
                    KafkaCheckpoint.objects.get_or_create(
                        checkpoint_id=new_checkpoint_id,
                        topic=topic,
                        partition=partition,
                        offset=min_offset
                    )
                print("\t{}, {}, {}".format(topic, partition, min_offset))
