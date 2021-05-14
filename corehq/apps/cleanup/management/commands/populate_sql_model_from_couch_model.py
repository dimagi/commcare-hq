import logging
import sys
import traceback

from django.core.management.base import BaseCommand, CommandError
from django.core.management import call_command
from django.db import transaction

from corehq.dbaccessors.couchapps.all_docs import get_all_docs_with_doc_types, get_doc_count_by_type
from corehq.util.couchdb_management import couch_config
from corehq.util.django_migrations import skip_on_fresh_install

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
        """
        This should find and update the sql object that corresponds to the given doc,
        or create it if it doesn't yet exist. This method is responsible for saving
        the sql object.
        """
        raise NotImplementedError()

    @classmethod
    def diff_couch_and_sql(cls, couch, sql):
        """
        This should compare each attribute of the given couch document and sql object.
        Return a list of human-reaedable strings describing their differences, or None if the
        two are equivalent. The list may contain `None` or empty strings which will be filtered
        out before display.
        """
        raise NotImplementedError()

    @classmethod
    def diff_attr(cls, name, doc, obj, wrap_couch=None, wrap_sql=None, name_prefix=None):
        """
        Helper for diff_couch_and_sql
        """
        couch = doc.get(name, None)
        sql = getattr(obj, name, None)
        if wrap_couch:
            couch = wrap_couch(couch) if couch is not None else None
        if wrap_sql:
            sql = wrap_sql(sql) if sql is not None else None
        return cls.diff_value(name, couch, sql, name_prefix)

    @classmethod
    def diff_value(cls, name, couch, sql, name_prefix=None):
        if couch != sql:
            name_prefix = "" if name_prefix is None else f"{name_prefix}."
            return f"{name_prefix}{name}: couch value {couch!r} != sql value {sql!r}"

    @classmethod
    def diff_lists(cls, name, docs, objects, attr_list=None):
        diffs = []
        if len(docs) != len(objects):
            diffs.append(f"{name}: {len(docs)} in couch != {len(objects)} in sql")
        else:
            for couch_field, sql_field in list(zip(docs, objects)):
                if attr_list:
                    for attr in attr_list:
                        diffs.append(cls.diff_attr(attr, couch_field, sql_field, name_prefix=name))
                else:
                    diffs.append(cls.diff_value(name, couch_field, sql_field))
        return diffs

    @classmethod
    def count_items_to_be_migrated(cls):
        couch_count = get_doc_count_by_type(cls.couch_db(), cls.couch_doc_type())
        sql_count = cls.sql_class().objects.count()
        return couch_count - sql_count

    @classmethod
    def commit_adding_migration(cls):
        """
        This should be the merge commit of the pull request that adds the command to the commcare-hq repository.
        If this is provided, the failure message in migrate_from_migration will instruct users to deploy this
        commit before running the command.
        """
        return None

    @classmethod
    @skip_on_fresh_install
    def migrate_from_migration(cls, apps, schema_editor):
        """
            Should only be called from within a django migration.
            Calls sys.exit on failure.
        """
        to_migrate = cls.count_items_to_be_migrated()
        print(f"Found {to_migrate} {cls.couch_doc_type()} documents to migrate.")

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
            if cls.commit_adding_migration():
                print(f"""
                Run the following commands to run the migration and get up to date:

                    commcare-cloud <env> fab setup_limited_release --set code_branch={cls.commit_adding_migration()}

                    commcare-cloud <env> django-manage --release <release created by previous command> {command_name}

                    commcare-cloud <env> deploy commcare
                """)
            sys.exit(1)

    @classmethod
    def couch_db(cls):
        return couch_config.get_db(cls.couch_db_slug())

    def add_arguments(self, parser):
        parser.add_argument(
            '--verify-only',
            action='store_true',
            dest='verify_only',
            default=False,
            help="""
                Don't migrate anything, instead check if couch and sql data is identical.
            """,
        )
        parser.add_argument(
            '--skip-verify',
            action='store_true',
            dest='skip_verify',
            default=False,
            help="""
                Migrate even if verifcation fails. This is intended for usage only with
                models that don't support verification.
            """,
        )

    def handle(self, **options):
        verify_only = options.get("verify_only", False)
        skip_verify = options.get("skip_verify", False)

        if verify_only and skip_verify:
            raise CommandError("verify_only and skip_verify are mutually exclusive")

        self.doc_count = get_doc_count_by_type(self.couch_db(), self.couch_doc_type())
        self.diff_count = 0
        self.doc_index = 0

        logger.info("Found {} {} docs and {} {} models".format(
            self.doc_count,
            self.couch_doc_type(),
            self.sql_class().objects.count(),
            self.sql_class().__name__,
        ))
        for doc in get_all_docs_with_doc_types(self.couch_db(), [self.couch_doc_type()]):
            self.doc_index += 1
            if not verify_only:
                self._migrate_doc(doc)
            if not skip_verify:
                self._verify_doc(doc, exit=not verify_only)

        logger.info(f"Processed {self.doc_index} documents")
        if not skip_verify:
            logger.info(f"Found {self.diff_count} differences")

    @classmethod
    def get_diff_as_string(cls, couch, sql):
        diff = cls.diff_couch_and_sql(couch, sql)
        if isinstance(diff, list):
            diffs = list(filter(None, diff))
            diff = "\n".join(diffs) if diffs else None
        return diff

    def _verify_doc(self, doc, exit=True):
        try:
            couch_id_name = getattr(self.sql_class(), '_migration_couch_id_name', 'couch_id')
            obj = self.sql_class().objects.get(**{couch_id_name: doc["_id"]})
            diff = self.get_diff_as_string(doc, obj)
            if diff:
                logger.info(f"Doc {getattr(obj, couch_id_name)} has differences:\n{diff}")
                self.diff_count += 1
                if exit:
                    sys.exit(1)
        except self.sql_class().DoesNotExist:
            pass    # ignore, the difference in total object count has already been displayed

    def _migrate_doc(self, doc):
        logger.info("Looking at {} doc #{} of {} with id {}".format(
            self.couch_doc_type(),
            self.doc_index,
            self.doc_count,
            doc["_id"]
        ))
        with transaction.atomic():
            model, created = self.update_or_create_sql_object(doc)
            action = "Creating" if created else "Updated"
            logger.info("{} model for doc with id {}".format(action, doc["_id"]))
