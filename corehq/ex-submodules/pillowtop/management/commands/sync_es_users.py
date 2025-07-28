from django.core.management.base import BaseCommand
from corehq.dbaccessors.couchapps.all_docs import get_all_docs_with_doc_types
from corehq.apps.users.models import CouchUser
from corehq.apps.users.signals import update_user_in_es


class Command(BaseCommand):
    help = "Sync users in Elasticsearch with Couchdb (WebUser or CommCareUser)"

    def add_arguments(self, parser):
        parser.add_argument(
            '--doc_types',
            required=True,
            choices=['WebUser', 'CommCareUser'],
            help='Specify which user doc type to sync: "WebUser" or "CommCareUser"'
        )

    def handle(self, **options):
        doc_type = options['doc_types']
        user_docs = get_all_docs_with_doc_types(db=CouchUser.get_db(), doc_types=[doc_type])

        for user_doc in user_docs:
            update_user_in_es(None, CouchUser.wrap_correctly(user_doc))
