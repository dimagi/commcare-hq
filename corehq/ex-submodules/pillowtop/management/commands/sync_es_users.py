import os

from django.core.management.base import BaseCommand
from elasticsearch6.exceptions import NotFoundError

from corehq.dbaccessors.couchapps.all_docs import (
    get_all_docs_with_doc_types,
    get_doc_count_by_type
)
from corehq.apps.users.models import CouchUser
from corehq.apps.users.signals import update_user_in_es
from corehq.util.log import with_progress_bar


class Command(BaseCommand):
    help = "Sync users in Elasticsearch with Couchdb (WebUser or CommCareUser)"

    SYNC_ES_USERS_PROGRESS_FILENAME = 'sync_es_users_processed_doc_ids.txt'

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
        doc_count = get_doc_count_by_type(CouchUser.get_db(), doc_type)

        processed_ids = set()
        processed_count = 0
        try:
            with open(self.SYNC_ES_USERS_PROGRESS_FILENAME, 'r') as f:
                for line in f:
                    processed_ids.add(line.strip())
        except FileNotFoundError:
            pass

        with open(self.SYNC_ES_USERS_PROGRESS_FILENAME, 'a') as f:
            for user_doc in with_progress_bar(user_docs, doc_count):
                user_id = user_doc.get('_id')
                if user_id in processed_ids:
                    continue
                try:
                    update_user_in_es(None, CouchUser.wrap_correctly(user_doc))
                    f.write(user_id + '\n')
                    processed_count += 1
                    if processed_count % 100 == 0:
                        f.flush()
                except NotFoundError as e:
                    self.stdout.write(self.style.WARNING(
                        f"User not found in Elasticsearch: {user_doc.get('_id')} - {str(e)}"
                    ))
            f.flush()
        os.remove(self.SYNC_ES_USERS_PROGRESS_FILENAME)
