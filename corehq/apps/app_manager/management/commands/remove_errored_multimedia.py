import json
import logging

from django.core.management.base import BaseCommand

from couchdbkit import ResourceNotFound

from corehq.apps.app_manager.models import Application
from corehq.apps.es import app_adapter

logger = logging.getLogger('remove_errored_multimedia')


class Command(BaseCommand):
    help = 'Remove multimedia references that are causing errors in applications'

    def add_arguments(self, parser):

        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Only report errors without making changes'
        )

    def get_app_ids(self):
        file_path = '/home/cchq/doc_ids_with_invalid_paths.txt'
        with open(file_path, 'r') as f:
            return [line.strip() for line in f.readlines()]

    def find_invalid_multimedia_names(self, doc):
        keys = doc.get('multimedia', {}).keys()
        invalid_keys = []
        for key in keys:
            if '..' in key:
                invalid_keys.append(key)
        return invalid_keys

    def remove_invalid_multimedia_and_save(self, app, key):
        val = app['multimedia_map'].pop(key)
        log = {
            'app_id': app['_id'],
            'key': key,
            'multimedia': val
        }
        if not self.dry_run:
            Application.get_db().save_doc(app)
            self.logs.append(log)
            self.save_logs(log)
        else:
            logger.info("Dry run mode is enabled. Log would be - " + json.dumps(log))
        return val

    def save_logs(self, logs):
        with open(self.log_file_path, 'a') as f:
            json.dump(logs, f)
            f.write('\n')

    def save_to_es(self, logs):
        if self.dry_run:
            logger.info("Not saving entries to ES because dry run mode is enabled")
            return
        for log in logs:
            app = Application.get(log['app_id'])
            app_adapter.index(app)

    def handle(self, *args, **options):
        self.dry_run = options['dry_run']
        self.log_file_path = 'removed_multimedia.ndjson'
        self.logs = []
        app_ids = self.get_app_ids()
        for app_id in app_ids:
            try:
                app = Application.get_db().get(app_id)
                invalid_keys = self.find_invalid_multimedia_names(app)
                if not invalid_keys:
                    logger.info(f"Application {app_id} has no invalid multimedia names. Skipping...")
                    continue
                for key in invalid_keys:
                    self.remove_invalid_multimedia_and_save(app, key)
            except ResourceNotFound:
                logger.error(f"Application {app_id} is probably deleted")
            except Exception as e:
                logger.error(f"Error processing application {app_id}: {e}")
        self.save_to_es(self.logs)
