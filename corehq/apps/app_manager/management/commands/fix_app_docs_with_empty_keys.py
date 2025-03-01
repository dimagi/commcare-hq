from django.core.management.base import BaseCommand
from corehq.apps.es.apps import app_adapter
from corehq.apps.app_manager.models import Application

import json


class Command(BaseCommand):
    help = 'Fix app documents with empty keys in Elasticsearch.'

    def handle(self, *args, **options):
        ids_with_empty_keys = self.find_docs_with_empty_keys()
        self.write_ids_to_file(ids_with_empty_keys)
        self.fix_documents(ids_with_empty_keys)

    def find_docs_with_empty_keys(self):
        # Query Elasticsearch to find documents with empty keys
        ids_with_empty_keys = []
        query = {
            "query": {
                "match_all": {}
            }
        }
        # Count total documents
        total_docs = app_adapter.count(query)
        processed_docs = 0
        scroll = app_adapter.scroll(query, size=1000)
        for doc in scroll:
            processed_docs += 1
            if self.has_empty_keys(doc):
                ids_with_empty_keys.append(doc['_id'])
            # Print progress every 1000 documents
            if processed_docs % 1000 == 0:
                print(f"Processed {processed_docs}/{total_docs} documents...")
        print(f"Finished processing. Total documents with empty keys: {len(ids_with_empty_keys)}")
        return ids_with_empty_keys

    def write_ids_to_file(self, ids):
        with open('ids_with_empty_keys.json', 'w') as f:
            json.dump(ids, f)

    def fix_documents(self, ids):
        with open('ids_with_empty_keys.json', 'r') as f:
            ids = json.load(f)

        for doc_id in ids:
            try:
                app = Application.get(doc_id)
                app_json = self.remove_empty_keys(app)
                Application.wrap(app_json).save()
                print(f"Fixed document with ID: {doc_id}")
            except Exception as e:
                print(f"Error processing document with ID {doc_id}: {e}")

        print("All documents have been processed.")

    def log_deleted_keys(self, app_id, path, value):
        with open('deleted_keys_log.ndjson', 'a') as log_file:
            log_entry = {
                'app_id': app_id,
                'path': path,
                'value': json.dumps(value)
            }
            json.dump(log_entry, log_file)
            log_file.write('\n')

    def remove_empty_keys(self, doc, path=""):
        def clean_dict(d, current_path):
            if isinstance(d, dict):
                if '' in d:
                    self.log_deleted_keys(doc['_id'], current_path, d[''])
                    del d['']
                for key, value in d.items():
                    clean_dict(value, f"{current_path}/{key}")
            elif isinstance(d, list):
                for index, item in enumerate(d):
                    clean_dict(item, f"{current_path}[{index}]")

        if not isinstance(doc, dict):
            doc = doc.to_json()

        clean_dict(doc, path)

        return doc

    def has_empty_keys(self, doc):
        def check_empty_keys(d):
            if isinstance(d, dict):
                for key, value in d.items():
                    if key == "":
                        return True
                    if check_empty_keys(value):
                        return True
            elif isinstance(d, list):
                for item in d:
                    if check_empty_keys(item):
                        return True
            return False

        return check_empty_keys(doc)
