import logging
from django.core.management import BaseCommand, call_command

from corehq.apps.app_manager.dbaccessors import get_app
from corehq.apps.es.apps import AppES


logger = logging.getLogger('app_migration')
logger.setLevel('DEBUG')


class Command(BaseCommand):
    help = '''
        Migrate any non-migrated apps
    '''

    def handle(self, *args, **options):
        # Find all apps not yet using vellum case management
        app_query = AppES().is_build(False).term('vellum_case_management', False) \
                           .term('doc_type', 'Application').source(['domain', '_id'])

        hits = app_query.run().hits
        total = 0
        for hit in hits:
            call_command('migrate_app_to_cmitfb', hit['_id'])
            total = total + 1
        logger.info('done with migrate_all_apps_to_cmitfb, migrated {} apps'.format(total))
