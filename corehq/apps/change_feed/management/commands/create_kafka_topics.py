from django.core.management import BaseCommand

from corehq.apps.change_feed import topics
from corehq.apps.change_feed.connection import get_kafka_client


class Command(BaseCommand):

    def handle(self, **options):
        create_kafka_topics()


def create_kafka_topics():
    # Use async client rather than admin client because the latter
    # has no public API for automatic topic creation.
    with get_kafka_client() as client:
        client.poll(future=client.cluster.request_update())
        new_topics = set(topics.ALL) - client.cluster.topics()
        if new_topics:
            future = client.set_topics(new_topics)
            client.poll(future=future)
            if not future.succeeded():
                assert future.is_done
                raise future.exception
        for topic in topics.ALL:
            status = "created" if topic in new_topics else "already exists"
            print(f"topic {status}: {topic}")
