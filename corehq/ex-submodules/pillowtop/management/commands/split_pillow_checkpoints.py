import logging
import sys

from django.core.management.base import BaseCommand

from pillowtop.models import KafkaCheckpoint

logger = logging.getLogger('__name__')


class Command(BaseCommand):
    """Split a pillow into multiple"""

    def add_arguments(self, parser):
        parser.add_argument(
            'checkpoint_ids', nargs='+',
            help="Split the first pillow checkpoint into all others named"
        )

    def handle(self, checkpoint_ids, **options):
        from_checkpoint = checkpoint_ids[0]
        to_checkpoints = checkpoint_ids[1:]
        logging.info(f"Attempting to split {from_checkpoint} into {to_checkpoints}")

        if KafkaCheckpoint.objects.filter(checkpoint_id__in=to_checkpoints).exists():
            logging.error(f'Some of {to_checkpoints} already exist. Aborting pillow merging')
            sys.exit(1)

        checkpoints = KafkaCheckpoint.objects.filter(checkpoint_id=from_checkpoint)
        new_checkpoints = []

        for checkpoint in checkpoints:
            for to_checkpoint in to_checkpoints:
                new_checkpoints.append(
                    KafkaCheckpoint(
                        checkpoint_id=to_checkpoint,
                        topic=checkpoint.topic, partition=checkpoint.partition,
                        offset=checkpoint.offset
                    )
                )

        KafkaCheckpoint.objects.bulk_create(new_checkpoints)
