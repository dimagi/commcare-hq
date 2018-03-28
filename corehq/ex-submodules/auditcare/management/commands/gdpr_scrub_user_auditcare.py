from __future__ import absolute_import
from __future__ import unicode_literals
from django.core.management.base import BaseCommand
from auditcare.utils.export import get_auditcare_docs_by_username
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = """Scrub a username from auditcare for GDPR compliance"""

    def add_arguments(self, parser):
        parser.add_argument('username', help="Username to scrub")

    def handle(self, username, **options):
        new_username = "Redacted User (GDPR)"
        doc_list = get_auditcare_docs_by_username(username)
        print("==========Document list:{}".format(doc_list))
        if doc_list:
            for doc in doc_list:
                doc.user = new_username
                doc.save()
            logger.info("Updated username in {} documents.".format(len(doc_list)))
        else:
            logger.info("The user {} has no associated docs in auditcare.".format(username))
