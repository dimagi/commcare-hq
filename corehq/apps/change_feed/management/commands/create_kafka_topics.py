from django.core.management import BaseCommand

from corehq.apps.change_feed import topics
from corehq.apps.change_feed.connection import get_kafka_admin_client


class Command(BaseCommand):

    def handle(self, **options):
        create_kafka_topics()


def create_kafka_topics():
    with get_kafka_admin_client() as client:
        existing_topics = set(client.list_topics())
        new_topics = set(topics.ALL) - existing_topics
        if not new_topics:
            print('All topics exists')
            return

        client.create_topics(list(new_topics), timeout_ms=10 * 1000)
        print(f"Topics created: {','.join(new_topics)}")
