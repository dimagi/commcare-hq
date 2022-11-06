import logging

from django.core.management.base import BaseCommand

from ...models import AccessAudit, NavigationEventAudit

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = """Scrub a username from auditcare for GDPR compliance"""
    new_username = "Redacted User (GDPR)"

    def add_arguments(self, parser):
        parser.add_argument('username', help="Username to scrub")

    def handle(self, username, **options):
        def update_events(model):
            user_events = model.objects.filter(user=username)
            user_events.update(user=self.new_username)

        update_events(AccessAudit)
        update_events(NavigationEventAudit)
