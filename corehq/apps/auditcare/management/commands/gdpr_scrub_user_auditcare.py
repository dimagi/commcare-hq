import logging

from django.core.management.base import BaseCommand

from corehq.util.couch import DocUpdate, iter_update
from corehq.util.log import with_progress_bar

from ...models import NavigationEventAudit
from ...utils.export import navigation_event_ids_by_user

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = """Scrub a username from auditcare for GDPR compliance"""

    def add_arguments(self, parser):
        parser.add_argument('username', help="Username to scrub")

    def handle(self, username, **options):
        def update_username(event_dict):
            event_dict['user'] = new_username
            return DocUpdate(doc=event_dict)

        new_username = "Redacted User (GDPR)"
        event_ids = navigation_event_ids_by_user(username)
        iter_update(NavigationEventAudit.get_db(), update_username, with_progress_bar(event_ids, len(event_ids)))
