from datetime import datetime
import logging

from django.core.management import BaseCommand

from corehq.apps.app_manager.dbaccessors import wrap_app
from corehq.apps.app_manager.models import Application
from corehq.apps.es.apps import AppES
from dimagi.utils.parsing import ISO_DATETIME_FORMAT

logger = logging.getLogger('created_from_template_migration')


def _get_app_id(date_created):
    # Guess at version based on date downloaded, assuming most people would have downloaded whatever was latest
    date_created = datetime.strptime(date_created, ISO_DATETIME_FORMAT)
    if date_created > datetime(2020, 4, 1):
        return "fe922d12718b4f2f9b4f9b36205ee860"
    if date_created > datetime(2020, 3, 27):
        return "46b1b6e5e3f04a1e9ca12d05150ad948"
    return "828f651b0508423783d541240965c73a"


class Command(BaseCommand):
    help = '''
        Populates created_from_template on apps docs that were likely imported from the COVID app library,
        prior to analytics being added.
    '''

    def add_arguments(self, parser):
        parser.add_argument(
            '--commit',
            action='store_true',
            help="Actually runs the migration. Without this flag, just logs the apps that would be migrated."
        )

    def handle(self, commit, **options):
        logger.setLevel('DEBUG')

        start_date = datetime(2020, 3, 19)
        end_date = datetime(2020, 4, 4)
        app_query = AppES().term('doc_type', 'Application') \
                           .missing('created_from_template') \
                           .missing('family_id') \
                           .date_range('date_created', gt=start_date, lt=end_date)
        hits = app_query.run().hits
        logger.info(f"Pulled {len(hits)} apps from ES")

        hits = [h for h in hits if 'FFX' in h['name'] and len(h['modules']) == 9]
        logger.info(f"Filtered to {len(hits)} apps likely imported from app library")

        for hit in hits:
            app = wrap_app(Application.get_db().get(hit['_id']))
            app.created_from_template = _get_app_id(hit['date_created'])
            if commit:
                app.save(increment_version=False)

        logger.info(f"Done with backfill_created_from_template, commit={commit}")
