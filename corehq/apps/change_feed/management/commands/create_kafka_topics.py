from __future__ import print_function
from __future__ import absolute_import
from __future__ import unicode_literals
from django.core.management import BaseCommand
from corehq.apps.change_feed import topics
from corehq.apps.change_feed.connection import get_simple_kafka_client


class Command(BaseCommand):

    def handle(self, **options):
        create_kafka_topics()


def create_kafka_topics():
    with get_simple_kafka_client() as client:
        for topic in topics.ALL:
            if client.has_metadata_for_topic(topic):
                status = "already exists"
            else:
                client.ensure_topic_exists(topic, timeout=10)
                status = "created"
            print("topic {}: {}".format(status, topic))
