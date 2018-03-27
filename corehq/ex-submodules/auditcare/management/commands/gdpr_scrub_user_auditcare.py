from __future__ import absolute_import
from __future__ import unicode_literals
from django.core.management.base import BaseCommand

from auditcare.utils.export import get_docs_by_user


class Command(BaseCommand):
    help = """Scrub a username from auditcare for GDPR compliance"""

    def add_arguments(self, parser):
        parser.add_argument('username', help="Username to scrub")

    def handle(self, username, **options):
        new_username = "Redacted User (GDPR)"
        doc_list = get_docs_by_user(username)
        if doc_list:
            for doc in doc_list:
                doc.user = new_username
                doc.save()
        else:
            print("The user {} has no associated docs in auditcare.".format(username))
