import inspect
import json
import sys

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from kafka import KafkaConsumer, TopicPartition

from corehq.apps.change_feed.consumer.feed import change_from_kafka_message
from corehq.apps.change_feed.topics import (
    get_multi_topic_first_available_offsets,
)
from corehq.util.argparse_types import utc_timestamp
from corehq.util.log import with_progress_bar


class Command(BaseCommand):
    help = inspect.cleandoc("""
        Search the Kafka changes feed for documents matching certain criteria. This is
        particularly useful if you can refine the date range to a smaller section of the
        timeline.

        Matching changes are output as JSON to stdout.
    """)

    def add_arguments(self, parser):
        parser.add_argument('--topic', required=True)
        parser.add_argument('--doc-ids', help="CSV of doc ID to search for")
        parser.add_argument('--doc-id-file', help="Path to file with one ID per line")
        parser.add_argument('--doc-type', help="Doc type to match")
        parser.add_argument('--doc-subtype', help="Doc subtype (case type, form XMLNS) to match")
        parser.add_argument('--start-date', type=utc_timestamp,
                            help="Timestamp to start the search from. Defaults to the start of the Kafka feed."
                                 " Format as YYYY-MM-DD HH:MM:SS")
        parser.add_argument('--end-date', type=utc_timestamp,
                            help="Timestamp to end the search at. Defaults to the end of the Kafka feed."
                                 " Format as YYYY-MM-DD HH:MM:SS")

    def handle(self, **options):
        topic = options["topic"]

        doc_ids = options.get("doc_ids")
        if doc_ids:
            doc_ids = doc_ids.split(",")

        if options.get("doc_id_file"):
            if doc_ids:
                raise CommandError("Can not supply doc IDs via file and via command line")

            with open(options["doc_id_file"], "r") as f:
                doc_ids = [line.strip() for line in f.readlines()]

        if doc_ids:
            # encode to match kafka message key
            doc_ids = {str(doc_id).encode() for doc_id in doc_ids}

        doc_type = options.get("doc_type")
        doc_subtype = options.get("doc_subtype")

        start, end = options.get("start_date"), options.get("end_date")

        info = [f"Searching the '{topic}' Kafka topic for documents matching:"]
        if doc_ids:
            info.append(f"\t doc_ids (count): {len(doc_ids)}")
        if doc_type:
            info.append(f"\t        doc_type: {doc_type}")
        if doc_subtype:
            info.append(f"\t     doc_subtype: {doc_subtype}")
        if start:
            info.append(f"\t published after: {start}")
        if end:
            info.append(f"\tpublished before: {end}")
        info = "\n".join(info)
        self.stderr.write(f"{info}\n\n")

        partitions = [
            TopicPartition(topic, partition)
            for topic, partition in get_multi_topic_first_available_offsets([topic])
        ]

        consumer = get_consumer()

        consumer.assign(partitions)
        if start:
            self.stderr.write(f"Searching for best offsets to start based on start date: {start}\n")
            offsets = get_offsets(partitions, start)
            for partition in partitions:
                consumer.seek(partition, offsets[partition])
        else:
            consumer.seek_to_beginning(partitions)

        count = 0
        last_progress = None
        buffer = []
        for message in consumer:
            count += 1

            metadata = None
            if count % 1000 == 0:
                if buffer:
                    self.stdout.writelines(buffer)
                    self.stdout.flush()
                    buffer = []
                metadata = change_from_kafka_message(message).metadata
                timestamp = metadata.publish_timestamp
                if not last_progress or (timestamp - last_progress).total_seconds() > (3600 * 2):
                    self.stderr.write(f"\nExamined {count} changes. Current point: {timestamp}\n")
                    last_progress = timestamp

                if end and metadata.publish_timestamp > end:
                    break

            if doc_ids and message.key not in doc_ids:
                continue

            if not metadata:
                change = change_from_kafka_message(message)
                metadata = change.metadata

            if doc_type and metadata.document_type != doc_type:
                continue
            if doc_subtype and metadata.document_subtype != doc_subtype:
                continue

            if end and metadata.publish_timestamp > end:
                break

            output = metadata.to_json()
            output["partition"] = message.partition
            output["offset"] = message.offset
            buffer.append(f"{json.dumps(output)}\n")

        if buffer:
            self.stdout.writelines(buffer)
            self.stdout.flush()


def get_offsets(partitions, date_start):
    offsets = {}
    for partition in with_progress_bar(partitions, prefix="\tSearching", stream=sys.stderr):
        consumer = get_consumer()
        consumer.assign([partition])
        consumer.seek_to_beginning()
        end_offset = consumer.end_offsets([partition])[partition]

        start_offset = consumer.beginning_offsets([partition])[partition]
        predicate = get_offset_check_function(consumer, partition, date_start, 3600 * 3)
        offsets[partition] = _search(start_offset, end_offset, predicate)
    return offsets


def get_consumer():
    config = {
        'client_id': 'pillowtop_utils',
        'bootstrap_servers': settings.KAFKA_BROKERS,
        'auto_offset_reset': 'earliest',
        'enable_auto_commit': False,
        'api_version': settings.KAFKA_API_VERSION,
        'consumer_timeout_ms': 5000
    }

    return KafkaConsumer(**config)


def get_offset_check_function(consumer, tp, target_date, margin):
    """
    Creates a function that is used to evaluate a Kafka partition offset to determine
    if the offset is at, above or below the desired location (based on the target_date).


    :param consumer: Kafka consumer
    :param tp: TuplePartition that is being searched
    :param target_date: change published date that is being searched for
    :param margin: margin or error that should be tolerated (in seconds)
    :returns: A function that can be used as a predicate to the ``_search`` function.

    """

    def check_offset(offset, consumer=consumer, tp=tp, target_date=target_date, margin=margin):
        consumer.seek(tp, offset)
        message = next(consumer)
        change = change_from_kafka_message(message)
        diff = (change.metadata.publish_timestamp - target_date).total_seconds()
        if diff < 0 and abs(diff) < margin:
            return 0
        return diff

    return check_offset


def _search(left, right, predicate):
    """Simple binary search that uses the ``predicate`` function to determine direction of search"""
    if right >= left:

        mid = left + (right - left) // 2

        res = predicate(mid)
        if res == 0:
            return mid

        elif res > 1:
            return _search(left, mid - 1, predicate)
        else:
            return _search(mid + 1, right, predicate)
    else:
        return -1
