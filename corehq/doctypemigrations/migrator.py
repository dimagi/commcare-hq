from corehq.doctypemigrations.bulk_migrate import bulk_migrate
from corehq.doctypemigrations.models import DocTypeMigrationState
from dimagi.utils.couch.database import get_db


class Migrator(object):
    instances = {}

    def __init__(self, doc_types, source_db_name, target_db_name, slug):
        assert doc_types
        self.doc_types = list(doc_types)
        self.slug = slug
        self.source_db_name = source_db_name
        self.source_db = get_db(source_db_name)
        self.target_db_name = target_db_name
        self.target_db = get_db(target_db_name)
        self.data_dump_filename = '{}.log'.format(self.slug)
        # shared by the class
        self.instances[self.slug] = self

    def phase_1_bulk_migrate(self):
        self.record_seq(self._get_latest_source_seq(self.source_db))
        bulk_migrate(self.source_db, self.target_db, self.doc_types,
                     filename=self.data_dump_filename)

    def phase_2_replicate_continuously(self):
        pass

    def record_seq(self, seq):
        state, _ = DocTypeMigrationState.objects.get_or_create(slug=self.slug)
        state.original_seq = seq
        state.save()

    @staticmethod
    def _get_latest_source_seq(db):
        return db.info()['update_seq']
