"""Migrate attachments from couchdb to an external blob store

## Running migrations

Use the `run_blob_migration` management command to transfer attachments
on selected models from couchdb to the external blob database. Run the
command without arguments to get a list of possible migrations that
can be run:

    ./manage.py run_blob_migration

The migration may be done automatically when running `./manage.py migrate`
if there are only a few documents to be migrated. However, if there are
many documents to be migrated then the normal migration process will
stop and prompt you to run the blob migration manually before
continuing with the normal migration process.

## Writing new migrations

Complete each of the following steps when migrating a new set of couch
models' attachments to the blob database:

1. Add `BlobMixin` as a base class of each couch model with attachments
   to be migrated to the blob database. For each new `BlobMixin` model:

   a. The mixin must come before `Document` in the list of base classes.
   b. Add `_migrating_blobs_from_couch = True` to the class.
   c. Add `_blobdb_type_code = CODES.<type_code>` to the class, adding
      a new type code to `corehq.blobs.CODES` if necessary.
   d. Adapt any uses of the `_attachments` property to use `blobs`
      instead (this is more than a simple find and replace; see
      `corehq.blobs.mixin` for details).

2. Add a `Migrator` instance to the list of `MIGRATIONS` in
   `corehq/blobs/migrate.py`. It will look something like
   `Migrator("<your_slug>", [<list of new BlobMixin couch models>])`.
   Don't forget to add a test to verify that your migration actually
   works.

3. Deploy.

4. Run the management command to migrate attachments out of couch:
   `./manage.py run_blob_migration <your_slug>`

5. Remove `_migrating_blobs_from_couch = True` from each of your
   `BlobMixin` models.

6. Create a new django migration with the `makemigrations` management
   command:
   ```
   ./manage.py makemigrations --empty blobs
   ```
   Then modify the new migration, adding an operation:
   ```
   operations = [
       migrations.RunPython(*assert_migration_complete("<your_slug>"))
   ]
   ```
   Don't forget to put
   ```
   from corehq.blobs.migrate import assert_migration_complete
   
   ```
   at the top of the file.

7. Deploy.

That's it, you're done!
"""
from __future__ import print_function
from __future__ import absolute_import
from __future__ import unicode_literals
import json
import os
import traceback
from base64 import b64encode
from contextlib import contextmanager
from datetime import timedelta
from tempfile import mkdtemp
from io import open

import gevent
import six
from django.conf import settings
from gevent.pool import Pool
from gevent.queue import LifoQueue
from django.db.models import Q

from corehq.apps.domain import SHARED_DOMAIN
from corehq.blobs import get_blob_db
from corehq.blobs.exceptions import NotFound
from corehq.blobs.migrate_metadata import migrate_metadata
from corehq.blobs.migratingdb import MigratingBlobDB
from corehq.blobs.mixin import BlobHelper
from corehq.blobs.models import BlobMeta, BlobMigrationState
from corehq.dbaccessors.couchapps.all_docs import get_doc_count_by_type
from corehq.sql_db.util import get_db_alias_for_partitioned_doc
from corehq.util.doc_processor.couch import (
    CouchDocumentProvider, doc_type_tuples_to_dict
)
from corehq.util.doc_processor.couch import CouchProcessorProgressLogger
from corehq.util.doc_processor.sql import SqlDocumentProvider
from corehq.util.doc_processor.progress import DOCS_SKIPPED_WARNING, ProgressManager
from corehq.util.pagination import TooManyRetries
from couchdbkit import ResourceConflict
from corehq.form_processor.backends.sql.dbaccessors import ReindexAccessor

MIGRATION_INSTRUCTIONS = """
There are {total} documents that may have attachments, and they must be
migrated to a new blob database.

Run these commands to proceed with migrations:

./manage.py run_blob_migration {slug} --file=FILE
./manage.py migrate

Note: --file=FILE is optional and can be omitted if you do not want to
keep a copy of the couch documents, including attachments, that were
migrated.

See also:
https://github.com/dimagi/commcare-hq/blob/master/corehq/blobs/migrate.py
"""

BLOB_DB_NOT_CONFIGURED = """
Cannot get the blob database.

This often means that settings.SHARED_DRIVE_ROOT is not configured.
It should be set to a real directory. Update localsettings.py and
retry the migration.
"""

PROCESSING_COMPLETE_MESSAGE = """
{} of {} blobs were not found in the old blob database. It
is possible that some blobs were deleted as part of normal
operation during the migration if the migration took a long
time. However, it may be cause for concern if a majority of
the total number of migrated blobs were not found.
"""


def encode_content(data):
    if isinstance(data, six.text_type):
        data = data.encode("utf-8")
    return b64encode(data)


class BaseDocMigrator(object):

    def __init__(self, couchdb, filename=None, blob_helper=BlobHelper,
                 get_type_code=lambda doc: None):
        super(BaseDocMigrator, self).__init__()
        self.couchdb = couchdb
        self.dirpath = None
        self.filename = filename
        self.blob_helper = blob_helper
        self.get_type_code = get_type_code
        if filename is None:
            self.dirpath = mkdtemp()
            self.filename = os.path.join(self.dirpath, "export.txt")

    def __enter__(self):
        print("Migration log: {}".format(self.filename))
        self.backup_file = open(self.filename, 'wb')
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.backup_file.close()
        self.processing_complete()

    def write_backup(self, doc):
        self.backup_file.write('{}\n'.format(json.dumps(doc)).encode('utf-8'))
        self.backup_file.flush()

    def migrate(self, doc):
        """Migrate a single document

        :param doc: The document dict to be migrated.
        :returns: True if doc was migrated else False. If this returns False
        the document migration will be retried later.
        """
        raise NotImplementedError

    def processing_complete(self):
        if self.dirpath is not None:
            os.remove(self.filename)
            os.rmdir(self.dirpath)


class CouchAttachmentMigrator(BaseDocMigrator):

    shared_domain = False

    def migrate(self, doc):
        self._prepare_doc(doc)
        self._backup_doc(doc)

        attachments = doc.pop("_attachments")
        external_blobs = doc.setdefault("external_blobs", {})
        obj = self.blob_helper(doc, self.couchdb, self.get_type_code(doc))
        try:
            with obj.atomic_blobs():
                for name, data in list(six.iteritems(attachments)):
                    if name in external_blobs:
                        continue  # skip attachment already in blob db
                    if self.shared_domain:
                        data = data.copy()
                        data["domain"] = SHARED_DOMAIN
                    obj.put_attachment(name=name, **data)
        except ResourceConflict:
            # Do not migrate document if `atomic_blobs()` fails.
            # This is an unlikely state, but could happen if the
            # document is (externally) modified between when the
            # migration fetches and processes the document.
            return False
        return True

    def should_process(self, doc):
        return doc.get("_attachments")

    def _prepare_doc(self, doc):
        obj = self.blob_helper(doc, self.couchdb, self.get_type_code(doc))
        doc["_attachments"] = {
            name: {
                "content_type": meta["content_type"],
                "content": obj.fetch_attachment(name),
            }
            for name, meta in doc["_attachments"].items()
        }

    def _backup_doc(self, doc):
        # make copy with encoded attachments for JSON dump
        backup_doc = dict(doc)
        backup_doc["_attachments"] = {
            name: {
                "content_type": meta["content_type"],
                "content": encode_content(meta["content"]),
            }
            for name, meta in doc["_attachments"].items()
        }
        self.write_backup(backup_doc)


class SharedCouchAttachmentMigrator(CouchAttachmentMigrator):

    shared_domain = True


class BlobDbBackendMigrator(BaseDocMigrator):
    """Migrate blobs from one blob db to another

    The backup log for this migrator will contain one JSON object
    for each blob that was not found in the old blob db.
    """

    def __init__(self, *args, **kw):
        super(BlobDbBackendMigrator, self).__init__(*args, **kw)
        self.db = get_blob_db()
        self.total_blobs = 0
        self.not_found = 0
        if not isinstance(self.db, MigratingBlobDB):
            raise MigrationError(
                "Expected to find migrating blob db backend (got %r)" % self.db)

    def migrate(self, doc):
        meta = doc["_obj_not_json"]
        self.total_blobs += 1
        try:
            content = self.db.old_db.get(key=meta.key)
        except NotFound:
            if not self.db.new_db.exists(key=meta.key):
                self.save_backup(doc)
        else:
            with content:
                self.db.copy_blob(content, key=meta.key)
        return True

    def save_backup(self, doc, error="not found"):
        meta = doc["_obj_not_json"]
        self.write_backup({
            "blobmeta_id": meta.id,
            "domain": meta.domain,
            "type_code": meta.type_code,
            "parent_id": meta.parent_id,
            "blob_key": meta.key,
            "error": error,
        })
        self.not_found += 1

    def processing_complete(self):
        super(BlobDbBackendMigrator, self).processing_complete()
        if self.not_found:
            print(PROCESSING_COMPLETE_MESSAGE.format(self.not_found, self.total_blobs))
            if self.dirpath is None:
                print("Missing blob ids have been written in the log file:")
                print(self.filename)


class BlobDbBackendCheckMigrator(BlobDbBackendMigrator):
    def migrate(self, doc):
        meta = doc["_obj_not_json"]
        self.total_blobs += 1
        if not self.db.new_db.exists(key=meta.key):
            try:
                content = self.db.old_db.get(key=meta.key)
            except NotFound:
                self.save_backup(doc)
            else:
                with content:
                    self.db.copy_blob(content, key=meta.key)
        return True


class BlobMetaReindexAccessor(ReindexAccessor):

    model_class = BlobMeta
    id_field = 'id'
    date_range = None

    def get_doc(self, *args, **kw):
        # only used for retries; BlobDbBackendMigrator doesn't retry
        raise NotImplementedError

    def doc_to_json(self, obj):
        return {"_id": obj.id, "_obj_not_json": obj}

    def get_key(self, doc):
        obj = doc["_obj_not_json"]
        assert isinstance(obj.id, six.integer_types), (type(obj.id), obj.id)
        # would use a tuple, but JsonObject.to_string requires dict keys to be strings
        return "%s %s" % (obj.parent_id, obj.id)

    def extra_filters(self, for_count=False):
        filters = list(super(BlobMetaReindexAccessor, self).extra_filters(for_count))
        if self.date_range is not None:
            start_date, end_date = self.date_range
            if start_date is not None:
                filters.append(Q(created_on__gte=start_date))
            if end_date is not None:
                one_day = timedelta(days=1)
                filters.append(Q(created_on__lt=end_date + one_day))
        return filters

    def load(self, key):
        parent_id, doc_id = key.rsplit(" ", 1)
        dbname = get_db_alias_for_partitioned_doc(parent_id)
        obj = self.model_class.objects.using(dbname).get(id=int(doc_id))
        return self.doc_to_json(obj)


class Migrator(object):

    has_worker_pool = False

    def __init__(self, slug, doc_types, doc_migrator_class):
        self.slug = slug
        self.doc_migrator_class = doc_migrator_class
        self.doc_types = doc_types
        first_type = doc_types[0]
        first_type = (first_type[0] if isinstance(first_type, tuple) else first_type)
        self.couchdb = first_type.get_db() if hasattr(first_type, "get_db") else None

        doc_types_map = doc_type_tuples_to_dict(self.doc_types)
        sorted_types = sorted(doc_types_map)
        self.iteration_key = "{}-blob-migration/{}".format(self.slug, " ".join(sorted_types))

        def get_type_code(doc):
            if doc_types_map:
                return doc_types_map[doc["doc_type"]]._blobdb_type_code
            return None
        self.get_type_code = get_type_code

    def migrate(self, filename=None, reset=False, max_retry=2, chunk_size=100, **kw):
        if 'date_range' in kw:
            doc_provider = self.get_document_provider(date_range=kw['date_range'])
        else:
            doc_provider = self.get_document_provider()
        iterable = doc_provider.get_document_iterator(chunk_size)
        progress = ProgressManager(
            iterable,
            total=doc_provider.get_total_document_count(),
            reset=reset,
            chunk_size=chunk_size,
            logger=CouchProcessorProgressLogger(self.doc_types),
        )
        if self.has_worker_pool:
            assert "iterable" not in kw, kw
            kw.update(iterable=iterable, max_retry=max_retry)

        with self.get_doc_migrator(filename, **kw) as migrator, progress:
            for doc in iterable:
                success = migrator.migrate(doc)
                if success:
                    progress.add()
                else:
                    try:
                        iterable.retry(doc, max_retry)
                    except TooManyRetries:
                        progress.skip(doc)

        if not progress.skipped:
            self.write_migration_completed_state()

        return progress.total, progress.skipped

    def write_migration_completed_state(self):
        BlobMigrationState.objects.get_or_create(slug=self.slug)[0].save()

    def get_doc_migrator(self, filename):
        return self.doc_migrator_class(
            self.couchdb,
            filename,
            get_type_code=self.get_type_code,
        )

    def get_document_provider(self):
        return CouchDocumentProvider(self.iteration_key, self.doc_types)


class BackendMigrator(Migrator):

    has_worker_pool = True

    def __init__(self, slug, doc_migrator_class):
        reindexer = BlobMetaReindexAccessor()
        types = [reindexer.model_class]
        assert not hasattr(types[0], "get_db"), types[0]  # not a couch model
        super(BackendMigrator, self).__init__(slug, types, doc_migrator_class)
        self.reindexer = reindexer

    def get_doc_migrator(self, filename, date_range=None, **kw):
        migrator = super(BackendMigrator, self).get_doc_migrator(filename)
        return _migrator_with_worker_pool(migrator, self.reindexer, **kw)

    def get_document_provider(self, date_range=None):
        iteration_key = self.iteration_key
        if date_range:
            (start, end) = date_range
            self.reindexer.date_range = date_range
            iteration_key = '{}-{}-{}'.format(self.iteration_key, start, end)
        return SqlDocumentProvider(iteration_key, self.reindexer)


@contextmanager
def _migrator_with_worker_pool(migrator, reindexer, iterable, max_retry, num_workers):
    """Migrate in parallel with worker pool

    When running in steady state, failed doc will be retried up to the
    max retry limit. Documents awaiting retry and all documents that
    started the migration process but did not finish will be saved and
    retried on the next run if the migration is stopped before it
    completes.
    """
    def work_on(doc, key, retry_count):
        try:
            ok = migrator.migrate(doc)
            assert ok, "run_with_worker_pool expects success!"
        except Exception:
            err = traceback.format_exc().strip()
            print("Error processing blob:\n{}".format(err))
            if retry_count < max_retry:
                print("will retry {}".format(key))
                retry_blobs[key] += 1
                queue.put(doc)
                return
            migrator.save_backup(doc, "too many retries")
            print("too many retries {}".format(key))
        retry_blobs.pop(key, None)

    def retry_loop():
        for doc in queue:
            enqueue_doc(doc)

    def enqueue_doc(doc):
        key = reindexer.get_key(doc)
        retry_count = retry_blobs.setdefault(key, 0)
        # pool.spawn will block until a worker is available
        pool.spawn(work_on, doc, key, retry_count)
        # Returning True here means the underlying iterator will think
        # this doc has been processed successfully. Therefore we must
        # process this doc before the process exits or save it to be
        # processed on the next run.
        return True

    queue = LifoQueue()
    loop = gevent.spawn(retry_loop)
    pool = Pool(size=num_workers)

    class gmigrator:
        migrate = staticmethod(enqueue_doc)

    with migrator:
        retry_blobs = iterable.get_iterator_detail("retry_blobs") or {}
        for key in list(retry_blobs):
            queue.put(reindexer.load(key))
        try:
            yield gmigrator
        finally:
            try:
                print("waiting for workers to stop... (Ctrl+C to abort)")
                queue.put(StopIteration)
                loop.join()
                while not pool.join(timeout=10):
                    print("waiting for {} workers to stop...".format(len(pool)))
            finally:
                iterable.set_iterator_detail("retry_blobs", retry_blobs)
                print("done.")


MIGRATIONS = {m.slug: m for m in [
    BackendMigrator("migrate_backend", BlobDbBackendMigrator),
    BackendMigrator("migrate_backend_check", BlobDbBackendCheckMigrator),
    migrate_metadata,
    # Kept for reference when writing new migrations.
    # Migrator("applications", [
    #    apps.Application,
    #    apps.RemoteApp,
    #    ("Application-Deleted", apps.Application),
    #    ("RemoteApp-Deleted", apps.RemoteApp),
    # ], CouchAttachmentMigrator),
]}


def assert_migration_complete(slug):

    def forwards(apps, schema_editor):
        if settings.UNIT_TESTING:
            return

        try:
            get_blob_db()
        except Exception:
            raise MigrationError(
                "Cannot get blob db:\n{error}{message}".format(
                    error=traceback.format_exc(),
                    message=BLOB_DB_NOT_CONFIGURED,
                ))

        try:
            BlobMigrationState.objects.get(slug=slug)
            return  # already migrated
        except BlobMigrationState.DoesNotExist:
            pass

        migrator = MIGRATIONS[slug]
        total = 0
        for doc_type, model_class in doc_type_tuples_to_dict(migrator.doc_types).items():
            total += get_doc_count_by_type(model_class.get_db(), doc_type)
        if total > 500:
            message = MIGRATION_INSTRUCTIONS.format(slug=slug, total=total)
            raise MigrationNotComplete(message)

        # just do the migration if the number of documents is small
        migrated, skipped = migrator.migrate()
        if skipped:
            raise MigrationNotComplete(DOCS_SKIPPED_WARNING.format(skipped))

    def reverse(apps, schema_editor):
        # NOTE: this does not move blobs back into couch. It only
        # un-sets the blob migration state so it can be run again.
        # It is safe to run the forward migration more than once.
        try:
            model = BlobMigrationState.objects.get(slug=slug)
            model.delete()
        except BlobMigrationState.DoesNotExist:
            pass

    return forwards, reverse


class MigrationError(Exception):
    pass


class MigrationNotComplete(MigrationError):
    pass
