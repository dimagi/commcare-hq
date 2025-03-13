import json
import os

from django.core.management.base import BaseCommand

from corehq.apps.app_manager.models import Application
from corehq.apps.es.apps import app_adapter


class Command(BaseCommand):
    help = 'Fix app documents with empty keys in Elasticsearch.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--rollback',
            action='store_true',
            help='Rollback changes made by this command using the deleted_keys_log.ndjson file',
        )
        parser.add_argument(
            '--find-only',
            action='store_true',
            help='Only find documents with empty keys and save their IDs to the ids-file without fixing them',
        )
        parser.add_argument(
            '--fix-only',
            action='store_true',
            help='Only fix documents using IDs from the ids-file without searching for documents',
        )
        parser.add_argument(
            '--log-file',
            default='deleted_keys_log.ndjson',
            help='Path to the log file for storing/retrieving deleted keys (default: deleted_keys_log.ndjson)',
        )
        parser.add_argument(
            '--ids-file',
            default='ids_with_empty_keys.json',
            help='Path to the file for storing/retrieving document IDs (default: ids_with_empty_keys.json)',
        )

    def handle(self, *args, **options):
        self.log_file = options.get('log_file', 'deleted_keys_log.ndjson')
        self.ids_file = options.get('ids_file', 'ids_with_empty_keys.json')

        if options['rollback']:
            self.rollback_changes()
        elif options['find_only']:
            self.stdout.write(self.style.SUCCESS("Starting to find documents with empty keys..."))
            ids_with_empty_keys = self.find_docs_with_empty_keys()
            self.write_ids_to_file(ids_with_empty_keys)
            self.stdout.write(
                self.style.SUCCESS(f"Find step completed. IDs saved to: {self.ids_file}")
            )
        elif options['fix_only']:
            if not os.path.exists(self.ids_file):
                self.stdout.write(
                    self.style.ERROR(f"No IDs file found at {self.ids_file}. Run with --find-only first.")
                )
                return
            self.stdout.write(self.style.SUCCESS(f"Starting to fix documents using IDs from {self.ids_file}..."))
            with open(self.ids_file, 'r') as f:
                ids_with_empty_keys = json.load(f)
            self.fix_documents(ids_with_empty_keys)
            self.stdout.write(
                self.style.SUCCESS(f"Fix step completed. Log file: {self.log_file}")
            )
        else:
            self.stdout.write(self.style.SUCCESS("Starting to find and fix documents with empty keys..."))
            ids_with_empty_keys = self.find_docs_with_empty_keys()
            self.write_ids_to_file(ids_with_empty_keys)
            self.fix_documents(ids_with_empty_keys)
            self.stdout.write(
                self.style.SUCCESS(f"Process completed. Log file: {self.log_file}, IDs file: {self.ids_file}")
            )

    def rollback_changes(self):
        """Restore empty keys that were removed using the log file"""
        if not os.path.exists(self.log_file):
            self.stdout.write(
                self.style.ERROR(f"No log file found at {self.log_file}. Cannot rollback changes.")
            )
            return

        self.stdout.write(self.style.SUCCESS(f"Starting rollback using log file: {self.log_file}"))

        total_apps = self.count_total_apps_with_empty_keys()
        failed_apps = []
        restored_apps = 0
        with open(self.log_file, 'r') as log_file:
            for line in log_file:
                try:
                    entry = json.loads(line)
                    self.add_back_empty_keys_and_save(entry)
                    restored_apps += 1
                    self.stdout.write(
                        self.style.SUCCESS(f"Restored : {entry['app_id']} ({restored_apps}/{total_apps})")
                    )
                except json.JSONDecodeError:
                    self.stdout.write(self.style.WARNING(f"Skipping invalid log entry: {line}"))
                    failed_apps.append(line)

        self.stdout.write(
            self.style.SUCCESS(
                f"Rollback completed. Restored {restored_apps} out of {total_apps} apps. \n"
                f"Failed to restore: \n{failed_apps}"
            )
        )

    def count_total_apps_with_empty_keys(self):
        with open(self.log_file, 'r') as log_file:
            return sum(1 for line in log_file)

    def add_back_empty_keys_and_save(self, change):
        app = Application.get(change['app_id'])
        app_json = app.to_json()
        current = app_json
        for part in change['path']:
            current = current[part]
        current[''] = change['value']
        Application.wrap(app_json).save()

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
                self.stdout.write(f"Processed {processed_docs}/{total_docs} documents...")
        self.stdout.write(
            self.style.SUCCESS(f"Finished processing. Total documents with empty keys: {len(ids_with_empty_keys)}")
        )
        return ids_with_empty_keys

    def write_ids_to_file(self, ids):
        with open(self.ids_file, 'w') as f:
            json.dump(ids, f)
        self.stdout.write(self.style.SUCCESS(f"Wrote {len(ids)} document IDs to {self.ids_file}"))

    def fix_documents(self, ids):
        total_docs = len(ids)
        fixed_docs = 0

        for i, doc_id in enumerate(ids):
            try:
                app = Application.get(doc_id)
                app_json = self.remove_empty_keys(app)
                Application.wrap(app_json).save()
                fixed_docs += 1
                self.stdout.write(
                    self.style.SUCCESS(f"Fixed document with ID: {doc_id} ({i+1}/{total_docs})")
                )
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Error processing document with ID {doc_id}: {e}"))

        self.stdout.write(
            self.style.SUCCESS(
                f"All documents have been processed. Fixed {fixed_docs} out of {total_docs} documents."
            )
        )

    def log_deleted_keys(self, app_id, path, value):
        with open(self.log_file, 'a') as log_file:
            log_entry = {
                'app_id': app_id,
                'path': path,
                'value': value
            }
            json.dump(log_entry, log_file)
            log_file.write('\n')

    def remove_empty_keys(self, doc, path=None):
        if path is None:
            path = []

        def clean_dict(d, current_path):
            if isinstance(d, dict):
                if '' in d:
                    self.log_deleted_keys(doc['_id'], current_path, d[''])
                    del d['']
                for key, value in list(d.items()):
                    new_path = current_path + [key]
                    clean_dict(value, new_path)
            elif isinstance(d, list):
                for index, item in enumerate(d):
                    new_path = current_path + [index]
                    clean_dict(item, new_path)

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
