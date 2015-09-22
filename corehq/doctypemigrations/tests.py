from copy import deepcopy
from django.test import TestCase
from corehq.doctypemigrations.bulk_migrate import bulk_migrate
from corehq.doctypemigrations.migrator import Migrator
from corehq.doctypemigrations.models import DocTypeMigrationState
from dimagi.utils.couch.bulk import get_docs
from django.conf import settings


class TestDocTypeMigrations(TestCase):
    def setUp(self):
        self.migration = Migrator(
            slug='user_db_migration',
            source_db_name=None,
            target_db_name=settings.NEW_USERS_GROUPS_DB,
            doc_types=(
                'Group',
                'CommCareUser',
            )
        )
        self.docs = [
            {'doc_type': 'CommCareUser', 'username': 'johnny@example.com'},
            {'doc_type': 'CommCareUser', 'username': 'fatima@example.com'},
            {'doc_type': 'Group', 'name': 'User Group'},
        ]
        results = self.migration.source_db.bulk_save(self.docs)
        for doc, result in zip(self.docs, results):
            doc['_id'] = result['id']
            doc['_rev'] = result['rev']
        _sort_by_doc_id(self.docs)

    def tearDown(self):
        # have to copy because deleted_docs modifies the docs param in place
        d1 = deepcopy(self.docs)
        d2 = deepcopy(self.docs)
        self.migration.source_db.delete_docs(d1)
        self.migration.target_db.delete_docs(d2)

    def test_bulk_migrate(self):
        bulk_migrate(
            self.migration.source_db, self.migration.target_db,
            self.migration.doc_types,
            self.migration.data_dump_filename)
        actual_docs = _get_non_design_docs(self.migration.target_db)
        self.assertEqual(actual_docs, self.docs)

    def test_phase_1_bulk_migrate(self):
        self.migration.phase_1_bulk_migrate()
        actual_docs = _get_non_design_docs(self.migration.target_db)
        self.assertEqual(actual_docs, self.docs)
        state = DocTypeMigrationState.objects.get(slug=self.migration.slug)
        self.assertIsNotNone(state.original_seq)


def _get_non_design_docs(db):
    docs = get_docs(db, [result['id'] for result in db
                         if not result['id'].startswith('_design/')])
    _sort_by_doc_id(docs)
    return docs


def _sort_by_doc_id(lst):
    lst.sort(key=lambda doc: doc['_id'])
