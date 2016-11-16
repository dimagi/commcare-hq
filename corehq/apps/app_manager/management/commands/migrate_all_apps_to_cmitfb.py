import logging
from django.core.management import BaseCommand, call_command

from corehq.apps.es.apps import AppES


logger = logging.getLogger('app_migration')
logger.setLevel('DEBUG')


class Command(BaseCommand):
    help = '''
        Migrate any non-migrated apps
    '''

    def handle(self, *args, **options):
        ids = AppES().is_build(False).term('vellum_case_management', False) \
                     .term('doc_type', 'Application').get_ids()
        for id in ids:
            call_command('migrate_app_to_cmitfb', id)
        logger.info('done with migrate_all_apps_to_cmitfb, migrated {} apps'.format(len(ids)))
