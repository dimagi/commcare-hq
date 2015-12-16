import uuid
from django.test import TestCase
from corehq.apps.commtrack.models import CommtrackConfig
from corehq.apps.domain.dbaccessors import (
    get_doc_count_in_domain_by_class,
    get_doc_ids_in_domain_by_class,
    get_docs_in_domain_by_class,
    get_domain_ids_by_names,
)
from corehq.apps.domain.models import Domain
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

    def get_doc_count_in_domain_by_class(self):
        group = Group(domain=self.domain)
        group.save()
        self.addCleanup(group.delete)
        group2 = Group(domain=self.domain)
        group2.save()
        self.addCleanup(group2.delete)
        count = get_doc_count_in_domain_by_class(self.domain, Group)
        self.assertEqual(count, 2)

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

    def test_get_docs_in_domain_by_class(self):
        commtrack_config = CommtrackConfig(domain=self.domain)
        group = Group(domain=self.domain)
        xform = XFormInstance(domain=self.domain)
        commtrack_config.save()
        group.save()
        xform.save()
        self.addCleanup(commtrack_config.delete)
        self.addCleanup(group.delete)
        self.addCleanup(xform.delete)
        [commtrack_config_2] = get_docs_in_domain_by_class(self.domain, CommtrackConfig)
        self.assertEqual(commtrack_config_2.to_json(), commtrack_config.to_json())

    def test_get_doc_ids_in_domain_by_type_initial_empty(self):
        self.assertEqual(0, len(get_doc_ids_in_domain_by_type('some-domain', 'some-doc-type', self.db)))

    def test_get_doc_ids_in_domain_by_type_match(self):
        id = uuid.uuid4().hex
        doc = {
            '_id': id,
            'domain': 'match-domain',
            'doc_type': 'match-type',
        }
        self.db.save_doc(doc)
        ids = get_doc_ids_in_domain_by_type('match-domain', 'match-type', self.db)
        self.assertEqual(1, len(ids))
        self.assertEqual(id, ids[0])
        self.db.delete_doc(doc)

    def test_get_doc_ids_in_domain_by_type_nomatch(self):
        id = uuid.uuid4().hex
        doc = {
            '_id': id,
            'domain': 'match-domain',
            'doc_type': 'nomatch-type',
        }
        self.db.save_doc(doc)
        ids = get_doc_ids_in_domain_by_type('match-domain', 'match-type', self.db)
        self.assertEqual(0, len(ids))
        self.db.delete_doc(doc)

    def test_get_domain_ids_by_names(self):
        def _create_domain(name):
            domain = Domain(name=name)
            domain.save()
            self.addCleanup(domain.delete)
            return domain._id

        names = ['b', 'a', 'c']
        expected_ids = [_create_domain(name) for name in names]

        ids = get_domain_ids_by_names(names)
        self.assertEqual(ids, expected_ids)

        ids = get_domain_ids_by_names(names[:-1])
        self.assertEqual(ids, expected_ids[:-1])
