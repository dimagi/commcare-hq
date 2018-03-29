from __future__ import absolute_import
from __future__ import unicode_literals
from corehq.util.log import with_progress_bar
from django.core.management.base import BaseCommand
from auditcare.utils.export import get_auditcare_docs_by_username, get_num_auditcare_events_by_username
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = """Scrub a username from auditcare for GDPR compliance"""

    def add_arguments(self, parser):
        parser.add_argument('username', help="Username to scrub")

    def handle(self, username, **options):
        new_username = "Redacted User (GDPR)"
        num_docs_updated = 0
        for doc in with_progress_bar(get_auditcare_docs_by_username(username),
                                     length=get_num_auditcare_events_by_username(username)):
            doc.user = new_username
            doc.save()
            num_docs_updated += 1
        if num_docs_updated:
            logger.warning("Updated username in {} documents.".format(num_docs_updated))
        else:
            logger.warning("The user {} has no associated docs in auditcare.".format(username))
