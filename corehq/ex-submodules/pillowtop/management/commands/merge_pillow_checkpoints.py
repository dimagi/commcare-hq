import logging
import sys

from django.core.management.base import BaseCommand
from django.db.models import Count, Max, Min

from pillowtop import get_pillow_by_name
from pillowtop.models import KafkaCheckpoint

logger = logging.getLogger('__name__')


def confirm(msg):
    return input(msg) == 'y'


class Command(BaseCommand):
    """Merge multiple pillows into one"""

    def add_arguments(self, parser):
        parser.add_argument(
            'pillow_names', nargs='+',
            help="Merge all pillow checkpoints into the last one named"
        )

    def handle(self, pillow_names, **options):
        from_pillows = pillow_names[:-1]
        to_pillow = pillow_names[-1]
        logging.info(f"Attempting to merge {from_pillows} into {to_pillow}")

        from_checkpoints = [
            get_pillow_by_name(pillow).checkpoint.checkpoint_id
            for pillow in from_pillows
        ]
        to_checkpoint = get_pillow_by_name(to_pillow).checkpoint.checkpoint_id

        existing_checkpoints = list(
            KafkaCheckpoint.objects.filter(checkpoint_id=to_checkpoint)
                .values('checkpoint_id').annotate(Max('last_modified'))
        )
        if existing_checkpoints:
            print(f'{to_checkpoint} already exists:')
            for checkpoint in existing_checkpoints:
                print(f"{checkpoint['checkpoint_id']} last updated {checkpoint['last_modified__max']}")

            if not confirm("Do you want to continue and overwrite existing checkpoints? [y/n]"):
                sys.exit(1)

            if not confirm("Are you sure you want to DELETE existing checkpoints? [y/n]"):
                sys.exit(1)

            KafkaCheckpoint.objects.filter(checkpoint_id=to_checkpoint).delete()

        checkpoint_info = (
            KafkaCheckpoint.objects
            .filter(checkpoint_id__in=from_checkpoints)
            .values('topic', 'partition')
            .annotate(Min('offset'), Max('offset'), Count('checkpoint_id'))
        )
        number_checkpoints = checkpoint_info[0]['checkpoint_id__count']
        number_nonstandard_checkpoints = sum(
            1 for info in checkpoint_info
            if info['checkpoint_id__count'] != number_checkpoints
        )
        if number_nonstandard_checkpoints > 0:
            logger.error(
                f'Not all checkpoints have the same topics and partitions specified. '
                'Aborting pillow merging'
            )
            sys.exit(2)

        minimum_difference = min(
            info['offset__max'] - info['offset__min']
            for info in checkpoint_info
        )
        if minimum_difference < 0:
            logger.error("The minimum difference between checkpoints between pillows is less than zero")
            sys.exit(4)

        maximum_difference = max(
            info['offset__max'] - info['offset__min']
            for info in checkpoint_info
        )

        if maximum_difference > 0:
            logger.warning(f"At least one checkpoint will need to reprocess {maximum_difference} changes")
            if confirm("Is this amount of reprocessing acceptable y/N?"):
                sys.exit(3)
        else:
            logger.info("All pillows have the same offsets")

        for info in checkpoint_info:
            KafkaCheckpoint.objects.update_or_create(
                checkpoint_id=to_checkpoint,
                topic=info['topic'],
                partition=info['partition'],
                defaults={
                    'offset': info['offset__min']
                }
            )
        logger.info(f"{to_checkpoint} checkpoints created")
