from django.core.management import BaseCommand, CommandError
from kafka import TopicPartition

from corehq.apps.change_feed.consumer.feed import KafkaChangeFeed
from corehq.util.markup import SimpleTableWriter, TableRowFormatter, CSVRowFormatter
from pillowtop import get_all_pillow_instances


class Command(BaseCommand):
    help = 'Command to calculate Kafka topic and partition assignments to pillow processes'

    def add_arguments(self, parser):
        parser.add_argument('pillow_name', help='Name of pillow')
        parser.add_argument('process_count', type=int, help='Number of processes to divide partitions among')
        parser.add_argument('--csv', action='store_true', help="Write output as CSV")

    def handle(self, pillow_name, process_count, **options):
        all_pillows = get_all_pillow_instances()
        pillows = [
            pillow for pillow in all_pillows if pillow.pillow_id == pillow_name
        ]
        if not pillows:
            all_names = '\n\t'.join([pillow.pillow_id for pillow in all_pillows])
            raise CommandError(f'No pillow found: {pillow_name}.\n\t{all_names}')

        pillow = pillows[0]
        change_feed = pillow.get_change_feed()
        if not isinstance(change_feed, KafkaChangeFeed):
            raise CommandError(f"Pillow '{pillow_name}' is not a Kafka pillow")

        topic_partitions = []
        for topic in change_feed.topics:
            for partition in change_feed.consumer.partitions_for_topic(topic):
                topic_partitions.append(TopicPartition(topic, partition))

        topic_partitions.sort()
        process_assignments = [
            topic_partitions[num::process_count]
            for num in range(process_count)
        ]

        if options['csv']:
            row_formatter = CSVRowFormatter()
        else:
            row_formatter = TableRowFormatter([len(pillow_name) + 4, 10])

        writer = SimpleTableWriter(self.stdout, row_formatter)
        writer.write_table(['Pillow Process', 'Kafka Topics'], [
            [
                f'{pillow_name}:{process_num}',
                ', '.join([f'{tp.topic}-{tp.partition}' for tp in assignments])
            ]
            for process_num, assignments in enumerate(process_assignments)
        ])
