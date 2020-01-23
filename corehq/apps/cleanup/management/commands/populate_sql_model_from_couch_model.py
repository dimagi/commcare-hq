import logging

from django.core.management.base import BaseCommand
from django.db import transaction

from dimagi.utils.couch.database import iter_docs

from corehq.dbaccessors.couchapps.all_docs import get_doc_ids_by_class

logger = logging.getLogger(__name__)


class PopulateSQLCommand(BaseCommand):
    """
        Base class for migrating couch docs to sql models.
    """

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            dest='dry_run',
            default=False,
            help='Do not actually modify the database, just verbosely log what will happen',
        )

    @property
    def couch_class(self):
        raise NotImplementedError()

    @property
    def couch_key(self):
        raise NotImplementedError()

    @property
    def sql_class(self):
        raise NotImplementedError()

    def doc_key(self, doc):
        return {key: doc[key] for key in doc if key in self.couch_key}

    def update_or_create_sql_object(self, doc):
        raise NotImplementedError()

    def handle(self, dry_run=False, **options):
        log_prefix = "[DRY RUN] " if dry_run else ""

        couch_class = self.couch_class

        doc_ids = get_doc_ids_by_class(couch_class)
        logger.info("{}Found {} {} docs and {} {} models".format(
            log_prefix,
            len(doc_ids),
            couch_class.__name__,
            self.sql_class.objects.count(),
            self.sql_class.__name__,
        ))
        for doc in iter_docs(couch_class.get_db(), doc_ids):
            logger.info("{}Looking at doc with key {}".format(log_prefix, self.doc_key(doc)))
            with transaction.atomic():
                model, created = self.update_or_create_sql_object(doc)
                if not dry_run:
                    logger.info("{}{} model for doc with key {}".format(log_prefix,
                                                                        "Created" if created else "Updated",
                                                                        self.doc_key(doc)))
                    model.save()
                elif created:
                    model.delete()
