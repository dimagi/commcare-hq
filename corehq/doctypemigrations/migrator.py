from collections import namedtuple
from corehq.doctypemigrations.changes import stream_changes_forever
from corehq.doctypemigrations.continuous_migrate import ContinuousReplicator
from dimagi.utils.decorators.memoized import memoized
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
        self.source_db = get_db(source_db_name)
        self.target_db_name = target_db_name
        self.target_db = get_db(target_db_name)
        self.data_dump_filename = '{}.log'.format(self.slug)
        # shared by the class
        self.instances[self.slug] = self

    def phase_1_bulk_migrate(self):
        self._record_original_seq(self._get_latest_source_seq(self.source_db))
        bulk_migrate(self.source_db, self.target_db, self.doc_types,
                     filename=self.data_dump_filename)
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
