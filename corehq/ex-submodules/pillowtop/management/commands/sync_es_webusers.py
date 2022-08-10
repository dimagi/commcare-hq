from django.core.management.base import BaseCommand
from corehq.dbaccessors.couchapps.all_docs import get_all_docs_with_doc_types
from corehq.apps.users.models import CouchUser
from corehq.apps.users.signals import update_user_in_es


class Command(BaseCommand):
    help = "Sync web users in Elasticsearch with Couchdb"

    def handle(self, **options):
        web_users_docs = get_all_docs_with_doc_types(db=CouchUser.get_db(), doc_types=["WebUser"])

        for user_doc in web_users_docs:
            update_user_in_es(None, CouchUser.wrap_correctly(user_doc))
