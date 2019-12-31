import logging

from django.core.management.base import BaseCommand
from django.db import transaction

from dimagi.utils.couch.database import iter_docs

from corehq.apps.cloudcare.models import (
    SQLApplicationAccess,
    SQLAppGroup,
)
from corehq.dbaccessors.couchapps.all_docs import get_doc_ids_by_class

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = """
        Adds a SQLApplicationAccess for any ApplicationAccess doc that doesn't yet have one.
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

        try:
            from corehq.apps.cloudcare.models import ApplicationAccess
        except ImportError:
            return

        doc_ids = get_doc_ids_by_class(ApplicationAccess)
        logger.info("{}Found {} ApplicationAccess docs and {} SQLApplicationAccess models".format(
            log_prefix,
            len(doc_ids),
            SQLApplicationAccess.objects.count()
        ))
        for doc in iter_docs(ApplicationAccess.get_db(), doc_ids):
            logger.info("{}Creating model for domain {}".format(log_prefix, doc['domain']))
            with transaction.atomic():
                model, created = SQLApplicationAccess.objects.update_or_create(
                    domain=doc['domain'],
                    defaults={
                        "restrict": doc['restrict'],
                    },
                )
                model.sqlappgroup_set.all().delete()
                model.sqlappgroup_set.set([
                    SQLAppGroup(app_id=group['app_id'], group_id=group['group_id'])
                    for group in doc['app_groups']
                ], bulk=False)
                if not dry_run:
                    model.save()
                elif created:
                    model.delete()
