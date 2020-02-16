import logging
import sys
import traceback

from django.core.management.base import BaseCommand
from django.core.management import call_command
from django.db import transaction

from corehq.dbaccessors.couchapps.all_docs import get_all_docs_with_doc_types, get_doc_count_by_type
from corehq.util.couchdb_management import couch_config

logger = logging.getLogger(__name__)


class PopulateSQLCommand(BaseCommand):
    """
        Base class for migrating couch docs to sql models.

        Adds a SQL object for any couch doc that doesn't yet have one.
        Override all methods that raise NotImplementedError and, optionoally, couch_db_slug.
    """
    AUTO_MIGRATE_ITEMS_LIMIT = 1000

    @classmethod
    def couch_db_slug(cls):
        # Override this if couch model was not stored in the main commcarehq database
        return None

    @classmethod
    def couch_doc_type(cls):
        raise NotImplementedError()

    @classmethod
    def sql_class(self):
        raise NotImplementedError()

    def update_or_create_sql_object(self, doc):
        raise NotImplementedError()

    @classmethod
    def count_items_to_be_migrated(cls):
        couch_count = get_doc_count_by_type(cls.couch_db(), cls.couch_doc_type())
        sql_count = cls.sql_class().objects.count()
        return couch_count - sql_count

    @classmethod
    def migrate_from_migration(cls, apps, schema_editor):
        """
            Should only be called from within a django migration.
            Calls sys.exit on failure.
        """
        to_migrate = cls.count_items_to_be_migrated()
        migrated = to_migrate == 0
        if migrated:
            return

        command_name = cls.__module__.split('.')[-1]
        if to_migrate < cls.AUTO_MIGRATE_ITEMS_LIMIT:
            try:
                call_command(command_name)
                remaining = cls.count_items_to_be_migrated()
                if remaining != 0:
                    migrated = False
                    print(f"Automatic migration failed, {remaining} items remain to migrate.")
                else:
                    migrated = True
            except Exception:
                traceback.print_exc()
        else:
            print("Found {} items that need to be migrated.".format(to_migrate))
            print("Too many to migrate automatically.")

        if not migrated:
            print(f"""
                A migration must be performed before this environment can be upgraded to the latest version
                of CommCareHQ. This migration is run using the management command {command_name}.
            """)
            sys.exit(1)

    @classmethod
    def couch_db(cls):
        return couch_config.get_db(cls.couch_db_slug())

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

        logger.info("{}Found {} {} docs and {} {} models".format(
            log_prefix,
            get_doc_count_by_type(self.couch_db(), self.couch_doc_type()),
            self.couch_doc_type(),
            self.sql_class().objects.count(),
            self.sql_class().__name__,
        ))
        for doc in get_all_docs_with_doc_types(self.couch_db(), [self.couch_doc_type()]):
            logger.info("{}Looking at {} doc with id {}".format(
                log_prefix,
                self.couch_doc_type(),
                doc["_id"]
            ))
            with transaction.atomic():
                model, created = self.update_or_create_sql_object(doc)
                if not dry_run:
                    logger.info("{}{} model for doc with id {}".format(log_prefix,
                                                                        "Created" if created else "Updated",
                                                                        doc["_id"]))
                    model.save()
                elif created:
                    model.delete()
