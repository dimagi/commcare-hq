from __future__ import print_function
from __future__ import absolute_import
from __future__ import unicode_literals
from django.core.management import BaseCommand
from corehq.apps.change_feed import topics
from corehq.apps.change_feed.connection import get_kafka_client


class Command(BaseCommand):

    def handle(self, **options):
        client = get_kafka_client()
        current_topics = client.cluster.topics()
        for topic in topics.ALL:
            if topic in current_topics:
                status = "already exists"
            else:
                client.add_topic(topic)
                status = "created"
            print("topic {}: {}".format(status, topic))
