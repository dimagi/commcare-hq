from __future__ import print_function

from __future__ import absolute_import
from __future__ import unicode_literals
from django.core.management.base import BaseCommand
from kafka.common import TopicAndPartition

from pillowtop.models import (
    DjangoPillowCheckpoint, KafkaCheckpoint, str_to_kafka_seq, kafka_seq_to_str
)
from six.moves import input
from six.moves import range


class Command(BaseCommand):
    """
    Safely add kafka partitions and have pillows listen to them
    """
    help = "Safely add a kafka partitions"

    def add_arguments(self, parser):
        parser.add_argument('topic')
        parser.add_argument('num_partitions', type=int)

    def handle(self, topic, num_partitions, **options):
        stop_pillows = input("did you stop pillows? [y/n]")
        if stop_pillows not in ['y', 'yes']:
            print("then stop them")

        kafka_command = (
            "./kafka-topics.sh --alter --zookeeper <zk IP>:2181 --partitions={} --topic={}"
            .format(num_partitions, topic)
        )
        print(
            "The following command should be run as root on the kafka server. You will find"
            "the script in the kafka install directory (likely /opt/kafka/bin)"
            "If an error occurs about a port, you can prefix the command with JMX_PORT=9998"
        )
        added_partition = input("have you run {} ? [y/n]".format(kafka_command))
        if added_partition not in ['y', 'yes']:
            print("then run it on the kafka machine")

        checkpoints = (
            KafkaCheckpoint.objects
            .filter(topic=topic)
            .distinct('checkpoint_id')
            .values_list('checkpoint_id', flat=True)
        )

        for checkpoint in checkpoints:
            for partition in range(num_partitions):
                # use get or create so that we don't accidentally update
                # any kafka checkpoints that are further than django checkpoints.
                KafkaCheckpoint.objects.get_or_create(
                    checkpoint_id=checkpoint,
                    topic=topic,
                    partition=partition,
                    defaults={'offset': 0}
                )

        print("please restart the pillows")
