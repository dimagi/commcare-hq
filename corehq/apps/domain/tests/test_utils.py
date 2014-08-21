import uuid
from django.test import TestCase
from corehq.apps.domain.utils import get_doc_ids
from dimagi.utils.couch.database import get_db


class TestDomainUtils(TestCase):

    def setUp(self):
        self.db = get_db()

    def test_get_doc_ids_initial_empty(self):
        self.assertEqual(0, len(get_doc_ids('some-domain', 'some-doc-type')))

    def test_get_doc_ids_match(self):
        id = uuid.uuid4().hex
        doc = {
            '_id': id,
            'domain': 'match-domain',
            'doc_type': 'match-type',
        }
        self.db.save_doc(doc)
        ids = get_doc_ids('match-domain', 'match-type')
        self.assertEqual(1, len(ids))
        self.assertEqual(id, ids[0])
        self.db.delete_doc(doc)

    def test_get_doc_id_type_nomatch(self):
        id = uuid.uuid4().hex
        doc = {
            '_id': id,
            'domain': 'match-domain',
            'doc_type': 'nomatch-type',
        }
        self.db.save_doc(doc)
        ids = get_doc_ids('match-domain', 'match-type')
        self.assertEqual(0, len(ids))
        self.db.delete_doc(doc)

    def test_get_doc_id_type_nomatch(self):
        id = uuid.uuid4().hex
        doc = {
            '_id': id,
            'domain': 'nomatch-domain',
            'doc_type': 'match-type',
}
        self.db.save_doc(doc)
        ids = get_doc_ids('match-domain', 'match-type')
        self.assertEqual(0, len(ids))
        self.db.delete_doc(doc)
