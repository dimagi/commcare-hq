import datetime
import json
import os
import re
import sys
import traceback
from contextlib import nullcontext
from functools import partial

from attrs import define, field

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import IntegrityError, transaction

from corehq.apps.domain.dbaccessors import iterate_doc_ids_in_domain_by_type
from corehq.dbaccessors.couchapps.all_docs import (
    get_all_docs_with_doc_types,
    get_doc_count_by_type,
    get_doc_count_by_domain_type
)
from corehq.util.couchdb_management import couch_config
from corehq.util.django_migrations import skip_on_fresh_install
from corehq.util.log import with_progress_bar
from dimagi.utils.chunked import chunked
from dimagi.utils.couch.database import iter_docs
from dimagi.utils.couch.migration import disable_sync_to_couch


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

    '''DEPRECATED the presence of this method will revert to migrating
    documents one at a time rather than in bulk. NOTE this method is
    required if the Couch model's `_migration_sync_to_sql` method does
    not accept a `save=False` keyword argument.

    def update_or_create_sql_object(self, doc):
        """
        This should find and update the sql object that corresponds to the given doc,
        or create it if it doesn't yet exist. This method is responsible for saving
        the sql object.
        """
        raise NotImplementedError()
    '''

    def _should_migrate_in_bulk(self):
        return not hasattr(self, "update_or_create_sql_object")

    def should_ignore(self, doc):
        """Return true if the document should not be synced to SQL"""
        return False

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
    def get_filtered_diffs(cls, couch, sql):
        diffs = cls.diff_couch_and_sql(couch, sql)
        if isinstance(diffs, list):
            diffs = list(filter(None, diffs))
        return diffs

    @classmethod
    def get_diff_as_string(cls, couch, sql):
        diffs = cls.get_filtered_diffs(couch, sql)
        return "\n".join(diffs) if diffs else None

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
        parser.add_argument(
            '--fixup-diffs',
            dest='fixup_diffs',
            help="""
                Update rows in SQL that do not match their corresponding Couch
                doc. The value of this parameter should be a log file generated
                by a previous run of this command. Diffs recorded in the log
                will be re-checked and re-synced if they still exist.
            """,
        )
        parser.add_argument(
            '--domains',
            nargs='+',
            help="Only migrate documents in the specified domains",
        )
        parser.add_argument(
            '--chunk-size',
            type=int,
            default=100,
            help="Number of docs to fetch at once (default: 100).",
        )
        parser.add_argument(
            '--log-path',
            default="-" if settings.UNIT_TESTING else None,
            help="File path to write logs to. If not provided a default will be used."
        )
        parser.add_argument(
            '--append-log',
            action="store_true",
            help="Append to log file if it already exists."
        )

    def handle(self, chunk_size, fixup_diffs, **options):
        log_path = options.get("log_path")
        append_log = options.get("append_log", False)
        verify_only = options.get("verify_only", False)
        skip_verify = options.get("skip_verify", False)

        if not log_path:
            date = datetime.datetime.utcnow().strftime('%Y-%m-%dT%H-%M-%S.%f')
            command_name = self.__class__.__module__.split('.')[-1]
            log_path = f"{command_name}_{date}.log"

        if log_path != "-" and os.path.exists(log_path) and not append_log:
            raise CommandError(f"Log file already exists: {log_path}")

        if verify_only and skip_verify:
            raise CommandError("verify_only and skip_verify are mutually exclusive")

        self.diff_count = 0
        self.ignored_count = 0
        self.missing_in_sql_count = 0
        doc_index = 0

        if fixup_diffs:
            if not os.path.exists(fixup_diffs):
                raise CommandError(
                    "The value of --fixup-diffs should be the path of a "
                    "log file written by a previous run of this command. "
                    f"File not found: {fixup_diffs}"
                )
            docs = DiffDocs(fixup_diffs, self.couch_db(), chunk_size)
            doc_count = sql_doc_count = len(docs)
        elif options["domains"]:
            domains = options["domains"]
            doc_count = self._get_couch_doc_count_for_domains(domains)
            sql_doc_count = self._get_sql_doc_count_for_domains(domains)
            docs = self._iter_couch_docs_for_domains(domains, chunk_size)
        else:
            doc_count = self._get_couch_doc_count_for_type()
            sql_doc_count = self.sql_class().objects.count()
            docs = self._get_all_couch_docs_for_model(chunk_size)

        print(f"\n\nDetailed log output file: {log_path}")
        print("Found {} {} docs and {} {} models".format(
            doc_count,
            self.couch_doc_type(),
            sql_doc_count,
            self.sql_class().__name__,
        ))

        is_bulk = self._should_migrate_in_bulk() or fixup_diffs
        if is_bulk:
            # migrate docs in batches
            iter_items = partial(chunked, n=chunk_size, collection=list)
            migrate = partial(self._migrate_docs, fixup_diffs=fixup_diffs)
            verify = self._verify_docs
        else:
            # migrate one doc at a time (legacy mode)
            def iter_items(docs):
                return docs
            migrate = self._migrate_doc
            verify = self._verify_doc

        with self.open_log(log_path, append_log) as logfile:
            for item in iter_items(with_progress_bar(docs, length=doc_count, oneline=False)):
                if not verify_only:
                    migrate(item, logfile)
                if not skip_verify:
                    verify(item, logfile, exit=not verify_only)
                if not is_bulk:
                    doc_index += 1
                    if doc_index % 1000 == 0:
                        print(f"Diff count: {self.diff_count}")

        if not is_bulk:
            print(f"Processed {doc_index} documents")
        if self.ignored_count:
            print(f"Ignored {self.ignored_count} Couch documents")
        if not skip_verify:
            print(f"Found {self.diff_count} differences")
        if self.missing_in_sql_count > self.ignored_count:
            missing = self.missing_in_sql_count - self.ignored_count
            not_ignored = " (and not ignored)" if self.ignored_count else ""
            print(f"Unexpected: {missing} Couch documents were not found in SQL{not_ignored}")

    def _migrate_docs(self, docs, logfile, fixup_diffs):
        def update_log(action, doc_ids):
            for doc_id in doc_ids:
                logfile.write(f"{action} model for {couch_doc_type} with id {doc_id}\n")
        couch_doc_type = self.couch_doc_type()
        sql_class = self.sql_class()
        couch_class = sql_class._migration_get_couch_model_class()
        couch_id_name = getattr(sql_class, '_migration_couch_id_name', 'couch_id')
        couch_ids = [doc["_id"] for doc in docs]
        objs = sql_class.objects.filter(**{couch_id_name + "__in": couch_ids})
        if fixup_diffs:
            objs_by_couch_id = {obj._migration_couch_id: obj for obj in objs}
        else:
            objs_by_couch_id = {obj._migration_couch_id for obj in objs.only(couch_id_name)}
        creates = []
        updates = []
        ignored = []
        for doc in docs:
            if self.should_ignore(doc):
                ignored.append(doc)
                continue
            if doc["_id"] in objs_by_couch_id:
                if fixup_diffs:
                    obj = objs_by_couch_id[doc["_id"]]
                    if self.get_filtered_diffs(doc, obj):
                        updates.append(obj)
                    else:
                        continue  # already migrated
                else:
                    continue  # already migrated
            else:
                obj = sql_class()
                obj._migration_couch_id = doc["_id"]
                creates.append(obj)
            couch_class.wrap(doc)._migration_sync_to_sql(obj, save=False)
        if creates or updates:
            self._save(sql_class, creates, updates)
        update_log("Created", [obj._migration_couch_id for obj in creates])
        update_log("Updated", [obj._migration_couch_id for obj in updates])
        update_log("Ignored", [doc["_id"] for doc in ignored])
        self.ignored_count += len(ignored)

    def _save(self, sql_class, creates, updates):
        def attempt_save():
            with transaction.atomic(), disable_sync_to_couch(sql_class):
                sql_class.objects.bulk_create(creates)
                for obj in updates:
                    obj.save()

        def remove_concurrently_created_items(err):
            match = DUPLICATE_KEY.search(str(err))
            if match and match.group("table") == sql_class._meta.db_table:
                exclude_pks = set(
                    sql_class.objects.filter(pk__in=[x.pk for x in creates])
                    .values_list("pk", flat=True)
                )
                if exclude_pks:
                    creates[:] = [x for x in creates if x.pk not in exclude_pks]
                    print("Concurrently created:", exclude_pks)
                    return True
            return False

        max_attempts = 10
        for i in range(max_attempts + 1):
            try:
                attempt_save()
            except IntegrityError as err:
                if i < max_attempts and remove_concurrently_created_items(err):
                    continue  # try again
                raise
            break

    def _verify_docs(self, docs, logfile, exit=True):
        sql_class = self.sql_class()
        couch_id_name = getattr(sql_class, '_migration_couch_id_name', 'couch_id')
        couch_ids = [doc["_id"] for doc in docs]
        objs = sql_class.objects.filter(**{couch_id_name + "__in": couch_ids})
        objs_by_couch_id = {obj._migration_couch_id: obj for obj in objs}
        self.missing_in_sql_count += len(couch_ids) - len(objs_by_couch_id)
        diff_count = self.diff_count
        for doc in docs:
            obj = objs_by_couch_id.get(doc["_id"])
            if obj is not None:
                self._do_diff(doc, obj, logfile, exit=False)
        if diff_count != self.diff_count:
            print(f"Diff count: {self.diff_count}")

    def _do_diff(self, doc, obj, logfile, exit):
        diff = self.get_diff_as_string(doc, obj)
        if diff:
            logfile.write(DIFF_HEADER.format(json.dumps(doc['_id'])))
            logfile.write(diff)
            logfile.write("\n")
            self.diff_count += 1
            if exit:
                raise CommandError(f"Doc verification failed for {doc['_id']!r}. Exiting.")

    def _verify_doc(self, doc, logfile, exit=True):
        try:
            couch_id_name = getattr(self.sql_class(), '_migration_couch_id_name', 'couch_id')
            obj = self.sql_class().objects.get(**{couch_id_name: doc["_id"]})
            self._do_diff(doc, obj, logfile, exit)
        except self.sql_class().DoesNotExist:
            self.missing_in_sql_count += 1

    def _migrate_doc(self, doc, logfile):
        if self.should_ignore(doc):
            self.ignored_count += 1
            logfile.write(f"Ignored model for {self.couch_doc_type()} with id {doc['_id']}\n")
            return
        with transaction.atomic(), disable_sync_to_couch(self.sql_class()):
            model, created = self.update_or_create_sql_object(doc)
            action = "Creating" if created else "Updated"
            logfile.write(f"{action} model for {self.couch_doc_type()} with id {doc['_id']}\n")

    def _get_couch_doc_count_for_domains(self, domains):
        return sum(
            get_doc_count_by_domain_type(self.couch_db(), domain, self.couch_doc_type())
            for domain in domains
        )

    def _get_sql_doc_count_for_domains(self, domains):
        return self.sql_class().objects.filter(domain__in=domains).count()

    def _iter_couch_docs_for_domains(self, domains, chunk_size):
        for domain in domains:
            print(f"Processing data for domain: {domain}")
            doc_id_iter = iterate_doc_ids_in_domain_by_type(
                domain, self.couch_doc_type(), database=self.couch_db()
            )
            for doc in iter_docs(self.couch_db(), doc_id_iter, chunk_size):
                yield doc

    def _get_all_couch_docs_for_model(self, chunk_size):
        return get_all_docs_with_doc_types(
            self.couch_db(), [self.couch_doc_type()], chunk_size)

    def _get_couch_doc_count_for_type(self):
        return get_doc_count_by_type(self.couch_db(), self.couch_doc_type())

    @staticmethod
    def open_log(log_path, append_log):
        if log_path == "-":
            return nullcontext(sys.stdout)
        mode = "a" if append_log else "w"
        return open(log_path, mode)


DUPLICATE_KEY = re.compile(r'duplicate key value violates unique constraint "(?P<table>.+)_pkey"')
DIFF_HEADER = "Doc {} has differences:\n"


@define
class DiffDocs:
    path = field()
    couch_db = field()
    chunk_size = field()

    def __iter__(self):
        doc_ids = self._iter_doc_ids()
        yield from iter_docs(self.couch_db, doc_ids, self.chunk_size)

    def __len__(self):
        return sum(1 for x in self._iter_doc_ids(quiet=True))

    def _iter_doc_ids(self, quiet=False):
        prefix, suffix = DIFF_HEADER.split("{}")
        with open(self.path) as log:
            for line in log:
                if line.startswith(prefix) and line.endswith(suffix):
                    doc_id = line[len(prefix):-len(suffix)]
                    try:
                        yield json.loads(doc_id)
                    except Exception:
                        if not quiet:
                            print("WARNING ignored diff, bad doc id format:", doc_id)
