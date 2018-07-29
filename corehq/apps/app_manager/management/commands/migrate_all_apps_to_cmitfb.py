from __future__ import absolute_import
from __future__ import unicode_literals
import logging
from django.core.management import BaseCommand, call_command

from corehq.apps.es.apps import AppES
import six


logger = logging.getLogger('app_migration')
logger.setLevel('DEBUG')


class Command(BaseCommand):
    help = '''
        Migrate any non-migrated apps
    '''

    def add_arguments(self, parser):
        parser.add_argument(
            '--commit',
            action='store_true',
            help="Actually runs the migration. Without this flag, just logs the apps that would be migrated."
        )

    def handle(self, commit, **options):
        app_query = AppES().is_build(False).term('vellum_case_management', False) \
                           .term('doc_type', 'Application').size(500).source(['domain', '_id'])

        hits = app_query.run().hits
        logger.info('found {} apps to migrate'.format(len(hits)))

        failures = {}
        for hit in hits:
            try:
                call_command('migrate_app_to_cmitfb', hit['_id'], dry_run=not(commit), fail_hard=True)
            except Exception:
                failures[hit['_id']] = hit['domain']

        for id, domain in six.iteritems(failures):
            logger.info('Failed: {} in {}'.format(id, domain))
        logger.info('Total: {} successes, {} failures'.format(len(hits) - len(failures), len(failures)))
        logger.info('Done with migrate_all_apps_to_cmitfb')
