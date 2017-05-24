from __future__ import print_function

from django.core.management.base import BaseCommand
from kafka.common import TopicAndPartition

from pillowtop.models import (
    DjangoPillowCheckpoint, KafkaCheckpoint, str_to_kafka_seq, kafka_seq_to_str
)


class Command(BaseCommand):
    """
    Safely add kafka partitions and have pillows listen to them
    """
    help = "Safely add a kafka partitions"

    def add_arguments(self, parser):
        parser.add_argument('topic')
        parser.add_argument('num_partitions', type=int)

    def handle(self, topic, num_partitions, **options):
        stop_pillows = raw_input("did you stop pillows? [y/n]")
        if stop_pillows not in ['y', 'yes']:
            print("then stop them")

        kafka_command = (
            "./kafka-topics.sh --alter --zookeeper <zk IP>:2181 --partitions={} --topic={}"
            .format(num_partitions, topic)
        )
        added_partition = raw_input("have you run {} ? [y/n]".format(kafka_command))
        if added_partition not in ['y', 'yes']:
            print("then run it")

        for checkpoint in DjangoPillowCheckpoint.objects.filter(sequence_format='json'):
            try:
                kafka_seq = str_to_kafka_seq(checkpoint.sequence)
            except ValueError:
                print("unable to parse {}", checkpoint.checkpoint_id)
                continue

            topics = [tp.topic for tp in kafka_seq]
            if topic not in topics:
                print("topic does not exist in {}", checkpoint.checkpoint_id)
                continue

            changed = False
            for partition in range(num_partitions):
                tp = TopicAndPartition(topic, partition)
                if tp in kafka_seq:
                    continue
                else:
                    changed = True
                    kafka_seq[tp] = 0

            if changed:
                checkpoint.old_sequence = checkpoint.sequence
                checkpoint.sequence = kafka_seq_to_str(kafka_seq)
                checkpoint.save()

                for topic_partition, offset in kafka_seq.items():
                    # use get or create so that we don't accidentally update
                    # any kafka checkpoints that are further than django checkpoints.
                    KafkaCheckpoint.objects.get_or_create(
                        checkpoint_id=checkpoint.checkpoint_id,
                        topic=topic_partition.topic,
                        partition=topic_partition.partition,
                        defaults={'offset': offset}
                    )

        print("please restart the pillows")
