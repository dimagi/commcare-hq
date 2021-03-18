import logging

from django.core.management.base import BaseCommand

from ...utils.export import navigation_events_by_user

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = """Scrub a username from auditcare for GDPR compliance"""

    def add_arguments(self, parser):
        parser.add_argument('username', help="Username to scrub")

    def handle(self, username, **options):
        events = navigation_events_by_user(username)
        events.query.update(user="Redacted User (GDPR)")
