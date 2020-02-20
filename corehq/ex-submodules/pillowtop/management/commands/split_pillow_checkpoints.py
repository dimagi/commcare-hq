import logging
import sys

from django.core.management.base import BaseCommand
from django.db.models import Max

from pillowtop import get_pillow_by_name
from pillowtop.models import KafkaCheckpoint

logger = logging.getLogger('__name__')


def confirm(msg):
    return input(msg) == 'y'


class Command(BaseCommand):
    """Split a pillow into multiple"""

    def add_arguments(self, parser):
        parser.add_argument(
            'pillow_names', nargs='+',
            help="Split the first pillow checkpoint into all others named"
        )

    def handle(self, pillow_names, **options):
        from_pillow = pillow_names[0]
        to_pillows = pillow_names[1:]
        logging.info(f"Attempting to split {from_pillow} into {to_pillows}")

        from_checkpoint = get_pillow_by_name(from_pillow).checkpoint.checkpoint_id
        to_checkpoints = [
            get_pillow_by_name(pillow).checkpoint.checkpoint_id
            for pillow in to_pillows
        ]

        existing_checkpoints = list(
            KafkaCheckpoint.objects.filter(checkpoint_id__in=to_checkpoints)
            .values('checkpoint_id').annotate(Max('last_modified'))
        )
        if existing_checkpoints:
            print(f'Some of {to_checkpoints} already exist:')
            for checkpoint in existing_checkpoints:
                print(f"{checkpoint['checkpoint_id']} last updated {checkpoint['last_modified__max']}")

            if not confirm("Do you want to continue and overwrite existing checkpoints? [y/n]"):
                sys.exit(1)

            if not confirm("Are you sure you want to DELETE existing checkpoints? [y/n]"):
                sys.exit(1)

            KafkaCheckpoint.objects.filter(checkpoint_id__in=to_checkpoints).delete()

        checkpoints = KafkaCheckpoint.objects.filter(checkpoint_id=from_checkpoint)

        for checkpoint in checkpoints:
            for to_checkpoint in to_checkpoints:
                KafkaCheckpoint.objects.update_or_create(
                    checkpoint_id=to_checkpoint,
                    topic=checkpoint.topic,
                    partition=checkpoint.partition,
                    defaults={
                        'offset': checkpoint.offset
                    }
                )
