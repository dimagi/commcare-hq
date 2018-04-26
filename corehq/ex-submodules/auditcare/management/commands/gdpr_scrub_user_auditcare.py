from __future__ import absolute_import
from __future__ import unicode_literals
from corehq.util.log import with_progress_bar
from corehq.util.couch import iter_update, DocUpdate
from django.core.management.base import BaseCommand
from auditcare.utils.export import navigation_event_ids_by_user
import logging
from auditcare.models import NavigationEventAudit


logger = logging.getLogger(__name__)
NEW_USERNAME = "Redacted User (Right To Forget)"


class Command(BaseCommand):
    help = """Scrub a username from auditcare for GDPR compliance"""

    def add_arguments(self, parser):
        parser.add_argument('username', help="Username to scrub")

    def handle(self, username, **options):
        def update_username(event_dict):
            event_dict['user'] = NEW_USERNAME
            return DocUpdate(doc=event_dict)

        event_ids = navigation_event_ids_by_user(username)
        iter_update(NavigationEventAudit.get_db(), update_username, with_progress_bar(event_ids, len(event_ids)))
