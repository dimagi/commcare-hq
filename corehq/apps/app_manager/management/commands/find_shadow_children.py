import csv
import logging

from django.core.management import BaseCommand

from dimagi.utils.couch.database import iter_docs

from corehq.apps.app_manager.management.commands.helpers import get_all_app_ids
from corehq.apps.app_manager.models import Application

logger = logging.getLogger('app_migration')
logger.setLevel('DEBUG')


class Command(BaseCommand):
    help = "Find all apps that have unmigrated shadow children"

    def add_arguments(self, parser):
        parser.add_argument(
            '--csv-path',
            dest='csv_path',
            default=None,
            help='Write results to this CSV',
        )

        parser.add_argument(
            '--domain',
            help='Only check this domain',
        )

        parser.add_argument(
            '--include-builds',
            dest='include_builds',
            action='store_true',
            default=False,
            help='Check all builds'
        )

    def handle(self, **options):
        self.options = options
        app_ids = self.get_app_ids()
        unmigrated_apps = []
        for doc in iter_docs(Application.get_db(), app_ids):
            shadow_children = self._find_shadow_children(doc)
            if shadow_children:
                unmigrated_apps.append({
                    'domain': doc['domain'],
                    'app_name': doc['name'],
                    'app_id': doc['_id'],
                    'unmigrated_modules': shadow_children
                })
        if not unmigrated_apps:
            logger.info("No apps to migrate")
            return

        if self.options['csv_path'] is None:
            for unmigrated_app in unmigrated_apps:
                logger.info(unmigrated_app)
        else:
            with open(self.options['csv_path'], 'w', encoding='utf-8') as f:
                writer = csv.DictWriter(f, unmigrated_apps[0].keys())
                writer.writeheader()
                writer.writerows(unmigrated_apps)

        logger.info(f"{len(unmigrated_apps)} apps to migrate. Details in {self.options['csv_path']}")

    def _find_shadow_children(self, app_doc):
        source_module_ids = {
            m['source_module_id']: m['unique_id']
            for m in app_doc['modules'] if m.get('module_type', '') == 'shadow'
        }
        child_modules_of_sources = {
            m['unique_id'] for m in app_doc['modules']
            if m['root_module_id'] in source_module_ids
        }

        # Parent -> Child
        # ^source - ^source
        # Shadow -> Shadow Child

        # If there is a shadow child that exists
        # i.e. a module whose source_module_id is set to the child_module_sources

        # We only need those
        module_ids_to_create = child_modules_of_sources - set(source_module_ids.keys())
        return [
            m['name']['en'] for m in app_doc['modules'] if m['unique_id'] in module_ids_to_create
        ]

    def get_app_ids(self):
        return get_all_app_ids(
            domain=self.options.get('domain', None),
            include_builds=self.options.get('include_builds', False)
        )
