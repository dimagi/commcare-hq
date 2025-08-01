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

from dimagi.utils.couch.undo import DELETED_SUFFIX


class Command(BaseCommand):
    help = "Sync users in Elasticsearch with Couchdb (WebUser or CommCareUser)"

    def add_arguments(self, parser):
        parser.add_argument(
            '--doc_types',
            required=True,
            choices=['WebUser', 'CommCareUser'],
            help='Specify which user doc type to sync: "WebUser" or "CommCareUser"'
        )
        parser.add_argument(
            '--progress-key',
            required=False,
            default=None,
            help='Optional key to append to the checkpoint file (e.g., "myproject").'
        )

    def handle(self, **options):
        doc_type = options['doc_types']
        user_docs = get_all_docs_with_doc_types(db=CouchUser.get_db(), doc_types=[doc_type])
        doc_count = get_doc_count_by_type(CouchUser.get_db(), doc_type)

        base_filename = "sync_es_users_processed_doc_ids"
        progress_key = options.get('progress_key')

        if progress_key:
            progress_filename = f"{base_filename}__{progress_key}.txt"

            processed_ids = set()
            processed_count = 0
            try:
                with open(progress_filename, 'r') as f:
                    for line in f:
                        processed_ids.add(line.strip())
            except FileNotFoundError:
                pass

            with open(progress_filename, 'a') as f:
                for user_doc in with_progress_bar(user_docs, doc_count):
                    user_id = user_doc.get('_id')
                    try:
                        if user_doc.get('base_doc').endswith(DELETED_SUFFIX):
                            continue
                    except Exception as e:
                        self.stdout.write(self.style.ERROR(
                            f"Error getting user doc: {user_id} - {str(e)}"
                        ))
                        continue

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
                            f"User not found in Elasticsearch: {user_id} - {str(e)}"
                        ))
                    except Exception as e:
                        self.stdout.write(self.style.ERROR(
                            f"Error updating user in ES: {user_id} - {str(e)}"
                        ))
                        continue
                f.flush()
            os.remove(progress_filename)
        else:
            for user_doc in with_progress_bar(user_docs, doc_count):
                user_id = user_doc.get('_id')
                try:
                    update_user_in_es(None, CouchUser.wrap_correctly(user_doc))
                except NotFoundError as e:
                    self.stdout.write(self.style.WARNING(
                        f"User not found in Elasticsearch: {user_doc.get('_id')} - {str(e)}"
                    ))
