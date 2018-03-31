from __future__ import print_function

from __future__ import absolute_import
from __future__ import unicode_literals
from django.core.management.base import BaseCommand

from pillowtop.models import DjangoPillowCheckpoint, KafkaCheckpoint, str_to_kafka_seq


class Command(BaseCommand):
    """
    One off migration for kafka pillow checkpoints before partitioning
    """
    help = "Migrate the kafka pillow checkpoints"

    def handle(self, **options):
        for checkpoint in DjangoPillowCheckpoint.objects.filter(sequence_format='json'):
            try:
                kafka_seq = str_to_kafka_seq(checkpoint.sequence)
            except ValueError:
                print("unable to migrate {}", checkpoint.checkpoint_id)
            else:
                for topic_partition, offset in kafka_seq.items():
                    KafkaCheckpoint.objects.update_or_create(
                        checkpoint_id=checkpoint.checkpoint_id,
                        topic=topic_partition.topic,
                        partition=topic_partition.partition,
                        defaults={'offset': offset}
                    )
