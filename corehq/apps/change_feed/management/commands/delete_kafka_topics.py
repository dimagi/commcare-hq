from django.conf import settings
from django.core.management import BaseCommand

from kafka.admin import KafkaAdminClient

from corehq.apps.change_feed import topics
from corehq.apps.change_feed.connection import GENERIC_KAFKA_CLIENT_ID


class Command(BaseCommand):

    def handle(self, **options):
        delete_kafka_topics()


def delete_kafka_topics():
    admin_client = KafkaAdminClient(
        bootstrap_servers=settings.KAFKA_BROKERS,
        client_id=GENERIC_KAFKA_CLIENT_ID
    )
    admin_client.delete_topics(topics.ALL, timeout_ms=30_000)
