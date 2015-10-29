import uuid
from django.test import TestCase
from corehq.apps.domain.dbaccessors import get_doc_ids_in_domain_by_class
from corehq.apps.groups.models import Group
from corehq.apps.users.models import UserRole
from couchforms.models import XFormInstance
from corehq.apps.domain.dbaccessors import get_doc_ids_in_domain_by_type
from dimagi.utils.couch.database import get_db


class DBAccessorsTest(TestCase):

    @classmethod
    def setUpClass(cls):
        cls.domain = 'domain-domain'
        cls.db = get_db()

    def test_get_doc_ids_in_domain_by_class(self):
        user_role = UserRole(domain=self.domain)
        group = Group(domain=self.domain)
        xform = XFormInstance(domain=self.domain)
        user_role.save()
        group.save()
        xform.save()
        self.addCleanup(user_role.delete)
        self.addCleanup(group.delete)
        self.addCleanup(xform.delete)
        [doc_id] = get_doc_ids_in_domain_by_class(self.domain, UserRole)
        self.assertEqual(doc_id, user_role.get_id)

    def get_doc_ids_in_domain_by_type_initial_empty(self):
        self.assertEqual(0, len(get_doc_ids_in_domain_by_type('some-domain', 'some-doc-type')))

    def get_doc_ids_in_domain_by_type_match(self):
        id = uuid.uuid4().hex
        doc = {
            '_id': id,
            'domain': 'match-domain',
            'doc_type': 'match-type',
        }
        self.db.save_doc(doc)
        ids = get_doc_ids_in_domain_by_type('match-domain', 'match-type')
        self.assertEqual(1, len(ids))
        self.assertEqual(id, ids[0])
        self.db.delete_doc(doc)

    def get_doc_ids_in_domain_by_type_nomatch(self):
        id = uuid.uuid4().hex
        doc = {
            '_id': id,
            'domain': 'match-domain',
            'doc_type': 'nomatch-type',
        }
        self.db.save_doc(doc)
        ids = get_doc_ids_in_domain_by_type('match-domain', 'match-type')
        self.assertEqual(0, len(ids))
        self.db.delete_doc(doc)

    def get_doc_ids_in_domain_by_type_nomatch(self):
        id = uuid.uuid4().hex
        doc = {
            '_id': id,
            'domain': 'nomatch-domain',
            'doc_type': 'match-type',
}
        self.db.save_doc(doc)
        ids = get_doc_ids_in_domain_by_type('match-domain', 'match-type')
        self.assertEqual(0, len(ids))
        self.db.delete_doc(doc)
