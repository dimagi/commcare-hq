import logging

from django.core.management.base import BaseCommand

from corehq.apps.app_manager.util import get_app_id_from_form_unique_id
from corehq.apps.reminders.models import SurveyKeyword
from corehq.dbaccessors.couchapps.all_docs import (
    get_deleted_doc_ids_by_class,
    get_doc_ids_by_class,
)
from corehq.util.couch import DocUpdate, iter_update

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Populate any SurveyKeyword models that contain a form_unique_id with the associated app_id."

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            default=False,
            help='Do not actually modify the database, just verbosely log what will happen',
        )

    def handle(self, dry_run=False, **options):
        def _add_field(doc):
            updated = False
            log_prefix = "{} Domain {}, form unique_id {}".format("[DRY RUN]" if dry_run else "",
                                                                  doc['domain'],
                                                                  doc['form_unique_id'])

            if doc.get('form_unique_id', None) and not doc.get('app_id', None):
                doc['app_id'] = get_app_id_from_form_unique_id(doc['domain'], doc['form_unique_id'])
                if doc['app_id']:
                    updated = True
                    logger.info("{}: Updated {} to use app id {}".format(log_prefix, doc['_id'], doc['app_id']))
                else:
                    logger.info("{}: Could not find app".format(log_prefix))

            for action in doc.get('actions', []):
                if action.get('form_unique_id', None) and not action.get('app_id', None):
                    action['app_id'] = get_app_id_from_form_unique_id(doc['domain'], action['form_unique_id'])
                    if action['app_id']:
                        updated = True
                        logger.info("{}: Updated action in {} to use app id {}".format(log_prefix,
                                                                                       doc['_id'],
                                                                                       action['app_id']))
                    else:
                        logger.info("{}: Could not find app".format(log_prefix))

            if updated and not dry_run:
                return DocUpdate(doc)

        doc_ids = get_doc_ids_by_class(SurveyKeyword) + get_deleted_doc_ids_by_class(SurveyKeyword)
        iter_update(SurveyKeyword.get_db(), _add_field, doc_ids)
