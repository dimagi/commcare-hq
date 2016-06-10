from django.core.management import BaseCommand
from corehq.apps.change_feed import topics
from corehq.apps.change_feed.connection import get_kafka_client


class Command(BaseCommand):

    def handle(self, *args, **options):
        create_kafka_topics()


def create_kafka_topics():
    client = get_kafka_client()
    for topic in topics.ALL:
        if client.has_metadata_for_topic(topic):
            status = "already exists"
        else:
            client.ensure_topic_exists(topic, timeout=5)
            status = "created"
        print("topic {}: {}".format(status, topic))
