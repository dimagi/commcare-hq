from __future__ import absolute_import
from __future__ import unicode_literals
from collections import namedtuple
from time import sleep
from couchdbkit import ResourceNotFound
from corehq.dbaccessors.couchapps.all_docs import delete_all_docs_by_doc_type
from corehq.doctypemigrations.changes import stream_changes_forever
from corehq.doctypemigrations.continuous_migrate import ContinuousReplicator
from corehq.doctypemigrations.stats import get_doc_counts_per_doc_type
from memoized import memoized
from corehq.doctypemigrations.bulk_migrate import bulk_migrate
from corehq.doctypemigrations.models import DocTypeMigration, DocTypeMigrationCheckpoint
from dimagi.utils.couch.database import get_db

StatusUpdate = namedtuple('StatusUpdate',
                          ['changes_read', 'last_seq', 'caught_up'])


class Migrator(object):
    instances = {}

    def __init__(self, doc_types, source_db_name, target_db_name, slug):
        assert doc_types
        doc_types = list(doc_types)
        self.doc_types = doc_types + [doc_type + '-Deleted' for doc_type in doc_types]
        self.slug = slug
        self.source_db_name = source_db_name
        self._source_db = None
        self.target_db_name = target_db_name
        self._target_db = None
        # shared by the class
        self.instances[self.slug] = self

    @property
    def source_db(self):
        if not self._source_db:
            self._source_db = get_db(self.source_db_name)
        return self._source_db

    @property
    def target_db(self):
        if not self._target_db:
            self._target_db = get_db(self.target_db_name)
        return self._target_db

    def phase_1_bulk_migrate(self):
        self._record_original_seq(self._get_latest_source_seq(self.source_db))
        bulk_migrate(self.source_db, self.target_db, self.doc_types)
        self._record_seq(self.original_seq)

    def phase_2_continuous_migrate_interactive(self):
        last_seq = self.last_seq
        replicator = ContinuousReplicator(self.source_db, self.target_db, self.doc_types)
        changes = stream_changes_forever(db=self.source_db, since=last_seq)
        count = 0
        for change in changes:
            if change is Ellipsis:
                # all caught up
                if last_seq != self.last_seq:
                    replicator.commit()
                    self._record_seq(last_seq)
                yield StatusUpdate(changes_read=count, last_seq=last_seq, caught_up=True)
            else:
                count += 1
                last_seq = change.seq
                replicator.replicate_change(change)
                if replicator.should_commit():
                    replicator.commit()
                    self._record_seq(last_seq)
                    yield StatusUpdate(changes_read=count, last_seq=last_seq, caught_up=False)

    def erase_continuous_progress(self):
        DocTypeMigrationCheckpoint.objects.filter(migration=self._migration_model)
        self._record_seq(self.original_seq)

    def phase_3_clean_up(self):
        delete_all_docs_by_doc_type(self.source_db, self.doc_types)
        self._migration_model.cleanup_complete = True
        self._migration_model.save()

    def get_doc_counts(self):
        source_counts = get_doc_counts_per_doc_type(self.source_db, self.doc_types)
        target_counts = get_doc_counts_per_doc_type(self.target_db, self.doc_types)
        return [(self.source_db, source_counts), (self.target_db, target_counts)]

    def _record_original_seq(self, seq):
        self._migration_model.original_seq = seq
        self._migration_model.save()

    def _record_seq(self, seq):
        checkpoint = DocTypeMigrationCheckpoint(migration=self._migration_model, seq=seq)
        checkpoint.save()

    @staticmethod
    def _get_latest_source_seq(db):
        return db.info()['update_seq']

    @property
    @memoized
    def _migration_model(self):
        migration, _ = DocTypeMigration.objects.get_or_create(slug=self.slug)
        return migration

    @property
    def original_seq(self):
        return self._migration_model.original_seq

    @property
    def last_seq(self):
        checkpoints = (
            DocTypeMigrationCheckpoint.objects
            .filter(migration=self._migration_model).order_by('-timestamp'))[:1]
        try:
            checkpoint, = checkpoints
        except ValueError:
            return None
        return checkpoint.seq

    @property
    def cleanup_complete(self):
        return self._migration_model.cleanup_complete

    def docs_are_replicating(self):
        """Make a change in source_db and see if it appears in target_db."""
        source_db, target_db = self.source_db, self.target_db
        doc_id = "testing-replication-doc"
        test_doc = {"doc_type": self.doc_types[0],
                    "_id": doc_id,
                    "description": self.docs_are_replicating.__doc__}
        source_db.save_doc(test_doc)
        sleep(10)
        try:
            replicated_doc = target_db.get(doc_id)
        except ResourceNotFound:
            doc_replicated = False
        else:
            doc_replicated = True
            target_db.delete_doc(replicated_doc)
        source_db.delete_doc(test_doc)
        return doc_replicated
