import datetime
import json
import os
import pdb
import sys
import traceback
from collections import defaultdict
from contextlib import nullcontext
from functools import partial
from time import sleep

from attrs import define, field

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from corehq.dbaccessors.couchapps.all_docs import (
    get_doc_count_by_type,
    get_doc_count_by_domain_type
)
from corehq.util.couch_helpers import NoSkipArgsProvider
from corehq.util.couchdb_management import couch_config
from corehq.util.django_migrations import skip_on_fresh_install
from corehq.util.log import with_progress_bar
from corehq.util.pagination import (
    PaginationEventHandler,
    ResumableFunctionIterator,
    paginate_function,
)
from dimagi.utils.chunked import chunked
from dimagi.utils.couch.database import iter_docs, retry_on_couch_error
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

    def get_ids_to_ignore(self, docs):
        """Return a set of document ids that should be ignored by the migration

        One example of how this might be used is when there are
        documents in Couch that have been orphaned from their parent
        (the parent doc has been deleted), and they cannot be inserted
        into SQL because a foreign key constraint would fail.

        The default implementation returns an empty set, which means no
        documents will be ignored unless this method is overridden.
        """
        return set()

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
            for i, (couch_field, sql_field) in enumerate(zip(docs, objects)):
                prefix = f"{name}[{i}]"
                if attr_list:
                    for attr in attr_list:
                        diffs.append(cls.diff_attr(attr, couch_field, sql_field, name_prefix=prefix))
                else:
                    diffs.append(cls.diff_value(prefix, couch_field, sql_field))
        return diffs

    def handle_override_is_completed(self, override_is_completed):
        if override_is_completed == "yes":
            self._set_migration_completed()
        elif override_is_completed == "no":
            self._override_migration_status(is_completed=False)
        elif override_is_completed == "discard":
            self.discard_resume_state()
        else:
            self._avg_items_to_be_migrated()
        print(f"status={self.get_migration_status()}")
        print("Items to be migrated:", self.count_items_to_be_migrated())

    def _set_migration_completed(self):
        print(f"Prior status={self.get_migration_status()}")
        if self._avg_items_to_be_migrated() > 10:
            print("WARNING Some items may not have been migrated.")
            if input("Override anyway? [yN] ").lower() != "y":
                print("Aborted.")
                return
        self._override_migration_status(is_completed=True)

    def _override_migration_status(self, is_completed):
        status = self.get_migration_status()
        if is_completed == bool(status.get("is_completed")):
            return
        if not status.get("is_completed"):
            print("WARNING The command may not have run to completion.")
            if input("Override anyway? [yN] ").lower() != "y":
                print("Aborted.")
                return
        self._resume_iter_couch_view().set_iterator_detail("is_completed", is_completed)

    def _avg_items_to_be_migrated(self):
        def get_count():
            sleep(1)
            return self.count_items_to_be_migrated()
        print("Sampling items to be migrated...")
        counts = [get_count() for x in range(10)]
        print(f"counts={counts} avg={sum(counts) / len(counts)}")
        return max(sum(counts) / len(counts), 0)

    @classmethod
    def count_items_to_be_migrated(cls):
        status = cls.get_migration_status()
        if status.get("is_completed"):
            return 0
        couch_count = cls._get_couch_doc_count_for_type()
        ignored_count = status.get("ignored_count", 0)
        sql_count = cls.sql_class().objects.count()
        return couch_count - ignored_count - sql_count

    @classmethod
    def get_migration_status(cls):
        return cls._resume_iter_couch_view().state.progress

    @classmethod
    def discard_resume_state(cls):
        resume = cls._resume_iter_couch_view()
        if hasattr(resume.state, "_rev"):
            print(f"Discarding resume state: {resume.state}")
            resume.discard_state()

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
        to_migrate = max(cls.count_items_to_be_migrated(), 0)
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
of CommCare HQ. This migration is run using the management command {command_name}.
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
            help="Only migrate documents in the specified domains. "
                 "NOTE: domain migrations are not resumable.",
        )
        parser.add_argument(
            '--chunk-size',
            type=int,
            default=1000,
            help="Number of docs to fetch at once (default: 100).",
        )
        parser.add_argument(
            '--log-path',
            default="-" if settings.UNIT_TESTING else None,
            help="File or directory path to write logs to. If not provided a default will be used."
        )
        parser.add_argument(
            '--override-is-migration-completed',
            choices=["check", "yes", "no", "discard"],
            dest="override_is_completed",
            help="""
                Check or set migration completion status. Use to override
                the check performed by `migrate_from_migration` when the number
                of items to be migrated is volatile. Accepted values:
                check: check and print status,
                yes: set `count_items_to_be_migrated` to zero,
                no: remove override,
                discard: discard all migration state.
            """
        )
        parser.add_argument(
            '--debug',
            action='store_true',
            help="Debug uncaught exceptions.",
        )

    def handle(self, chunk_size, fixup_diffs, override_is_completed, debug, **options):
        if override_is_completed:
            if options["domains"]:
                raise CommandError("Cannot override status with --domains")
            return self.handle_override_is_completed(override_is_completed)

        log_path = options.get("log_path")
        verify_only = options.get("verify_only", False)
        skip_verify = options.get("skip_verify", False)

        if not log_path or os.path.isdir(log_path):
            date = datetime.datetime.utcnow().strftime('%Y-%m-%dT%H-%M-%S.%f')
            command_name = self.__class__.__module__.split('.')[-1]
            filename = f"{command_name}_{date}.log"
            log_path = os.path.join(log_path, filename) if log_path else filename

        if log_path != "-" and os.path.exists(log_path):
            raise CommandError(f"Log file already exists: {log_path}")

        if verify_only and skip_verify:
            raise CommandError("verify_only and skip_verify are mutually exclusive")

        self.diff_count = 0
        self.ignored_count = 0
        doc_index = 0
        offset = 0

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
            results = self._resume_iter_couch_view(chunk_size)
            if verify_only:
                # non-resumable iteration
                results = paginate_function(results.data_function, results.args_provider)
            else:
                # resumable iteration
                state = results.state.progress
                offset = state.get("doc_count", 0)
                if state.get("is_completed"):
                    print(f"Migration is complete. Previously migrated {offset} documents.")
                    print("Use --override-is-migration-completed to inspect or reset.")
                    return
                log_path = state.setdefault("log_path", str(log_path))
            should = self.should_process
            docs = (r['doc'] for r in results if should(r))
        docs = with_progress_bar(docs, doc_count, oneline=False, offset=offset)

        print("Detailed log output file:", log_path)
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

        aborted = False
        with self.open_log(log_path) as logfile:
            self.logfile = logfile
            try:
                for item in iter_items(docs):
                    if not verify_only:
                        migrate(item, logfile)
                    if not skip_verify:
                        verify(item, logfile, verify_only)
                    if not is_bulk:
                        doc_index += 1
                        if doc_index % 1000 == 0:
                            print(f"Diff count: {self.diff_count}")
            except KeyboardInterrupt:
                traceback.print_exc(file=logfile)
                aborted = True
                print("Aborted.")
            except Exception as exc:
                if not debug:
                    raise
                traceback.print_exception(type(exc), exc, exc.__traceback__)
                pdb.post_mortem(exc.__traceback__)
                aborted = True

        if not is_bulk:
            print(f"Processed {doc_index} documents")
        if self.ignored_count:
            print(f"Ignored {self.ignored_count} Couch documents")
        if not skip_verify:
            print(f"Found {self.diff_count} differences")
            if self.diff_count:
                print(f"\nRun again with --fixup-diffs={log_path} to resolve differences.")
        if aborted:
            sys.exit(1)

    def _migrate_docs(self, docs, logfile, fixup_diffs):
        def update_log(action, doc_ids):
            for doc_id in doc_ids:
                logfile.write(f"{action} model for {couch_doc_type} with id {doc_id}\n")

        def update_sub_creates(pairs):
            for sub_class, subs in pairs:
                if subs:
                    submodel_creates[sub_class].extend(subs)

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
        submodel_specs = couch_class._migration_get_submodels()
        submodel_creates = defaultdict(list)
        self._prepare_for_submodel_creation(docs)
        # cache ignored ids in instance variable so _verify_docs does not need to recalculate
        self._ignored_ids_cache = ignored = self.get_ids_to_ignore(
            [d for d in docs if d["_id"] not in objs_by_couch_id])
        self.ignored_count += len(ignored)
        for doc in docs:
            if doc["_id"] in ignored:
                continue
            if doc["_id"] in objs_by_couch_id:
                if submodel_specs:
                    update_sub_creates(self._create_submodels(doc, submodel_specs))
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
        if creates or updates or submodel_creates:
            with transaction.atomic(), disable_sync_to_couch(sql_class):
                # ignore conflicts when the PK value is not needed for submodels
                sql_class.objects.bulk_create(creates, ignore_conflicts=not submodel_specs)
                update_sub_creates(self._group_submodels(creates, submodel_specs))
                for sub_class, sub_creates in submodel_creates.items():
                    sub_class.objects.bulk_create(sub_creates)
                for obj in updates:
                    obj.save()
        update_log("Created", [obj._migration_couch_id for obj in creates])
        update_log("Updated", [obj._migration_couch_id for obj in updates])
        update_log("Ignored", ignored)

    def _prepare_for_submodel_creation(self, docs):
        """Populate caches or otherwise prepare for submodel creation"""
        pass

    def _create_submodels(self, doc, obj, submodel_specs):
        """Create (unsaved) submodels for a previously synced doc

        The default implementation does nothing, but this hook can be
        used by subclasses to implement submodel creation for models
        that do not sync submodels to SQL on every Couch document save.

        :returns: Iterable of ``(submodel_type, submodels_list)`` pairs.
        """
        return []

    def _group_submodels(self, creates, submodel_specs):
        combined = defaultdict(list)
        for spec in submodel_specs:
            for obj in creates:
                sql_submodels, manager = obj._new_submodels[spec.sql_class]
                if sql_submodels:
                    combined[spec.sql_class].extend(sql_submodels)
        return combined.items()

    def _sql_query_from_docs(self, docs):
        """Construct SQL query for records corresponding to the given docs

        Override to augment the query with ``prefetch_related()``
        for submodel query optimization, etc.
        """
        sql_class = self.sql_class()
        couch_id_name = getattr(sql_class, '_migration_couch_id_name', 'couch_id')
        couch_ids = [doc["_id"] for doc in docs]
        return sql_class.objects.filter(**{couch_id_name + "__in": couch_ids})

    def _verify_docs(self, docs, logfile, verify_only):
        objs = self._sql_query_from_docs(docs)
        objs_by_couch_id = {obj._migration_couch_id: obj for obj in objs}
        diff_count = self.diff_count
        if verify_only:
            ignored = self.get_ids_to_ignore(
                [d for d in docs if d["_id"] not in objs_by_couch_id])
            self.ignored_count += len(ignored)
        else:
            ignored = self._ignored_ids_cache
        for doc in docs:
            if doc["_id"] in ignored:
                continue
            self._do_diff(doc, objs_by_couch_id.get(doc["_id"]), logfile)
        if diff_count != self.diff_count:
            print(f"Diff count: {self.diff_count}")

    def _do_diff(self, doc, obj, logfile, exit=False):
        if obj is None:
            couch_class = self.sql_class()._migration_get_couch_model_class()
            if not couch_class.get_db().doc_exist(doc["_id"]):
                return  # ignore if also missing in Couch (deleted)
            diff = "Missing in SQL - unique constraint violation?"
        else:
            diff = self.get_diff_as_string(doc, obj)
        if diff:
            logfile.write(DIFF_HEADER.format(json.dumps(doc['_id'])))
            logfile.write(diff)
            logfile.write("\n")
            self.diff_count += 1
            if exit:
                raise CommandError(f"Doc verification failed for {doc['_id']!r}. Exiting.")

    def _verify_doc(self, doc, logfile, verify_only):
        ignored = self.get_ids_to_ignore([doc]) if verify_only else self._ignored_ids_cache
        if doc["_id"] in ignored:
            if verify_only:
                self.ignored_count += 1
            return
        try:
            couch_id_name = getattr(self.sql_class(), '_migration_couch_id_name', 'couch_id')
            obj = self.sql_class().objects.get(**{couch_id_name: doc["_id"]})
        except self.sql_class().DoesNotExist:
            obj = None
        self._do_diff(doc, obj, logfile, exit=not verify_only)

    def _migrate_doc(self, doc, logfile):
        # cache ignored ids in instance variable so _verify_doc does not need to recalculate
        self._ignored_ids_cache = ignored = self.get_ids_to_ignore([doc])
        if doc["_id"] in ignored:
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
        view_name, domains_params = self.get_couch_view_name_and_parameters_for_domains(domains)
        assert len(domains) == len(domains_params), (domains, domains_params)
        view = partial(self.couch_db().view, view_name, reduce=False, include_docs=True)
        should = self.should_process
        for domain, params in zip(domains, domains_params):
            print(f"Processing data for domain: {domain}")
            args_provider = NoSkipArgsProvider(params | {"limit": chunk_size})
            results = paginate_function(view, args_provider)
            yield from (r['doc'] for r in results if should(r))

    @classmethod
    def _resume_iter_couch_view(cls, chunk_size=1000):
        view_name, params = cls.get_couch_view_name_and_parameters()
        view = retry_on_couch_error(partial(
            cls.couch_db().view, view_name, reduce=False, include_docs=True))
        args_provider = NoSkipArgsProvider(params | {"limit": chunk_size})
        iteration_key = f"{cls.couch_doc_type()}-to-sql"
        rfi = ResumableFunctionIterator(iteration_key, view, args_provider)
        assert rfi.event_handler is None, rfi
        rfi.event_handler = IterDocsEvents(rfi)
        return rfi

    def should_process(self, result):
        """Return true if Couch result should be processed

        Can be used to filter out results with null document, for example.
        """
        return True

    @classmethod
    def get_couch_view_name_and_parameters(cls):
        """Get view name and parameters for all docs iteration

        Override if the all_docs/by_doc_type view does not exist in the
        target database.
        """
        doc_type = cls.couch_doc_type()
        return 'all_docs/by_doc_type', {
            'startkey': [doc_type],
            'endkey': [doc_type, {}],
        }

    @classmethod
    def get_couch_view_name_and_parameters_for_domains(cls, domains=None):
        """Get view name and parameters for all docs iteration

        Override if by_domain_doc_type_date/view does not exist or does
        not index the relevant documents in the target database.
        """
        doc_type = cls.couch_doc_type()
        return 'by_domain_doc_type_date/view', [{
            'startkey': [domain, doc_type],
            'endkey': [domain, doc_type, {}],
        } for domain in domains]

    @classmethod
    def _get_couch_doc_count_for_type(cls):
        return get_doc_count_by_type(cls.couch_db(), cls.couch_doc_type())

    @staticmethod
    def open_log(log_path, mode="a"):
        if log_path == "-":
            return nullcontext(sys.stdout)
        return open(log_path, mode)


DIFF_HEADER = "Doc {} has differences:\n"


class IterDocsEvents(PaginationEventHandler):

    def __init__(self, iterator):
        self.iterator = iterator
        self.initial_count = iterator.state.progress.get("doc_count", 0)

    def page_start(self, total_emitted, *args, **kwargs):
        self.iterator.state.progress["doc_count"] = self.initial_count + total_emitted

    def stop(self):
        self.iterator.set_iterator_detail("is_completed", True)


@define
class DiffDocs:
    path = field()
    couch_db = field()
    chunk_size = field()
    diff_template = field(default=DIFF_HEADER)

    def __iter__(self):
        doc_ids = self.iter_doc_ids()
        yield from iter_docs(self.couch_db, doc_ids, self.chunk_size)

    def __len__(self):
        return sum(1 for x in self.iter_doc_ids(quiet=True))

    def iter_doc_ids(self, quiet=False):
        prefix, suffix = self.diff_template.split("{}")
        with open(self.path) as log:
            for line in log:
                if line.startswith(prefix) and line.endswith(suffix):
                    doc_id = line[len(prefix):-len(suffix)]
                    try:
                        yield json.loads(doc_id)
                    except Exception:
                        if not quiet:
                            print("WARNING ignored diff, bad doc id format:", doc_id)
