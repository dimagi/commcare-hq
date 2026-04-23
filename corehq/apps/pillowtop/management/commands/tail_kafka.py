import inspect
import json

from django.conf import settings
from django.core.management.base import BaseCommand

from kafka import KafkaConsumer, TopicPartition

from corehq.apps.change_feed.consumer.feed import change_from_kafka_message
from corehq.apps.change_feed.topics import (
    get_multi_topic_first_available_offsets,
)


class Command(BaseCommand):
    help = inspect.cleandoc("""Log Kafka changes to stdout""")

    def add_arguments(self, parser):
        parser.add_argument('--topics', nargs="+", required=True)
        parser.add_argument('--doc-type', help="Doc type to match")
        parser.add_argument('--doc-subtype', help="Doc subtype (case type, form XMLNS) to match")

    def handle(self, **options):
        topics = options["topics"]

        doc_type = options.get("doc_type")
        doc_subtype = options.get("doc_subtype")

        info = [f"Outputting changes for the [{', '.join(topics)}] topics. Press Ctrl-C to exit."]
        if doc_type or doc_subtype:
            info.append("Document filters:")
        if doc_type:
            info.append(f"\t        doc_type: {doc_type}")
        if doc_subtype:
            info.append(f"\t     doc_subtype: {doc_subtype}")
        info = "\n".join(info)
        self.stderr.write(f"{info}\n\n")

        partitions = [
            TopicPartition(topic, partition)
            for topic, partition in get_multi_topic_first_available_offsets(topics)
        ]

        consumer = get_consumer()
        consumer.assign(partitions)
        consumer.seek_to_end(*partitions)

        try:
            while True:
                for message in consumer:
                    metadata = change_from_kafka_message(message).metadata

                    if doc_type and metadata.document_type != doc_type:
                        continue
                    if doc_subtype and metadata.document_subtype != doc_subtype:
                        continue

                    output = metadata.to_json()
                    output["partition"] = message.partition
                    output["offset"] = message.offset
                    self.stdout.write(f"{metadata.document_type}: {json.dumps(output)}\n")
                    self.stdout.flush()

                self.stdout.write("\nWaiting for changes...\n")
        except KeyboardInterrupt:
            return


def get_consumer():
    config = {
        'client_id': 'pillowtop_utils',
        'bootstrap_servers': settings.KAFKA_BROKERS,
        'auto_offset_reset': 'earliest',
        'enable_auto_commit': False,
        'api_version': settings.KAFKA_API_VERSION,
        'consumer_timeout_ms': 10000
    }

    return KafkaConsumer(**config)
