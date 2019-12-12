import logging

from django.core.management.base import BaseCommand

from dimagi.utils.couch.database import iter_docs

from corehq.apps.app_manager.models import (
    GlobalAppConfig,
    LATEST_APK_VALUE,
    LATEST_APP_VALUE,
    SQLGlobalAppConfig,
)
from corehq.dbaccessors.couchapps.all_docs import get_doc_ids_by_class

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = """
        Adds a SQLGlobalAppConfig for any GlobalAppConfig doc that doesn't yet have one.
    """

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            dest='dry_run',
            default=False,
            help='Do not actually modify the database, just verbosely log what will happen',
        )

    def handle(self, dry_run=False, **options):
        log_prefix = "[DRY RUN] " if dry_run else ""

        doc_ids = get_doc_ids_by_class(GlobalAppConfig)
        logger.info("{}Found {} GlobalAppConfig docs and {} SQLGlobalAppConfig models".format(
            log_prefix,
            len(doc_ids),
            SQLGlobalAppConfig.objects.count()
        ))
        for doc in iter_docs(GlobalAppConfig.get_db(), doc_ids):
            log_message = "{}Created model for domain {} app {}".format(log_prefix, doc['domain'], doc['app_id'])
            if dry_run:
                if not SQLGlobalAppConfig.objects.filter(domain=doc['domain'], app_id=doc['app_id']).exists():
                    logger.info(log_message)
            else:
                model, created = SQLGlobalAppConfig.objects.get_or_create(domain=doc['domain'],
                                                                          app_id=doc['app_id'])
                if created:
                    model.apk_prompt = doc['apk_prompt']
                    model.app_prompt = doc['app_prompt']
                    model.apk_version = doc.get('apk_version', LATEST_APK_VALUE)
                    model.app_version = doc.get('app_version', LATEST_APP_VALUE)
                    model.save()
                    logger.info(log_message)
