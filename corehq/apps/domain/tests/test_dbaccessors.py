import datetime
import functools
import uuid

from django.test import TestCase

from casexml.apps.case.models import CommCareCase
from corehq.apps.casegroups.models import CommCareCaseGroup
from couchforms.models import XFormInstance
from dimagi.utils.couch.database import get_db

from corehq.apps.domain.dbaccessors import (
    deleted_domain_exists,
    domain_exists,
    domain_or_deleted_domain_exists,
    get_doc_count_in_domain_by_class,
    get_doc_ids_in_domain_by_class,
    get_doc_ids_in_domain_by_type,
    get_docs_in_domain_by_class,
    get_domain_ids_by_names,
    iter_all_domains_and_deleted_domains_with_name,
    iterate_doc_ids_in_domain_by_type,
)
from corehq.apps.domain.models import Domain
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.groups.models import Group


class DBAccessorsTest(TestCase):

    @classmethod
    def setUpClass(cls):
        super(DBAccessorsTest, cls).setUpClass()
        cls.domain = 'domain-domain'
        cls.project = create_domain(cls.domain)
        cls.db = get_db()

    @classmethod
    def tearDownClass(cls):
        super(DBAccessorsTest, cls).tearDownClass()
        for snapshot in cls.project.snapshots():
            snapshot.delete()
        cls.project.delete()

    def test_get_doc_count_in_domain_by_class(self):
        case = CommCareCase(domain=self.domain, opened_on=datetime.datetime(2000, 1, 1))
        case.save()
        self.addCleanup(case.delete)
        case2 = CommCareCase(domain=self.domain, opened_on=datetime.datetime(2001, 1, 1))
        case2.save()
        self.addCleanup(case2.delete)

        get = functools.partial(
            get_doc_count_in_domain_by_class, self.domain, CommCareCase)

        self.assertEqual(get(), 2)

    def test_get_docs_in_domain_by_class(self):
        group = Group(domain=self.domain)
        case_group = CommCareCaseGroup(name='a group', domain=self.domain)
        group.save()
        case_group.save()
        self.addCleanup(group.delete)
        self.addCleanup(case_group.delete)
        [group2] = get_docs_in_domain_by_class(self.domain, Group)
        self.assertEqual(group2.to_json(), group.to_json())
        [case_group2] = get_docs_in_domain_by_class(self.domain, CommCareCaseGroup)
        self.assertEqual(case_group.to_json(), case_group2.to_json())

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

    def test_iterate_doc_ids_in_domain_by_type(self):
        id1 = uuid.uuid4().hex
        id2 = uuid.uuid4().hex
        id3 = uuid.uuid4().hex
        doc1 = {
            '_id': id1,
            'domain': 'match-domain',
            'doc_type': 'match-type',
        }
        doc2 = {
            '_id': id2,
            'domain': 'match-domain',
            'doc_type': 'match-type',
        }
        doc3 = {
            '_id': id3,
            'domain': 'match-domain',
            'doc_type': 'nomatch-type',
        }
        self.db.save_doc(doc1)
        self.db.save_doc(doc2)
        self.db.save_doc(doc3)

        self.addCleanup(self.db.delete_doc, doc1)
        self.addCleanup(self.db.delete_doc, doc2)
        self.addCleanup(self.db.delete_doc, doc3)

        ids = list(iterate_doc_ids_in_domain_by_type(
            'match-domain',
            'match-type',
            database=self.db,
            chunk_size=1))
        self.assertEqual(sorted(ids), sorted([id1, id2]))

    def test_get_domain_ids_by_names(self):
        def _create_domain(name):
            domain = Domain(name=name)
            domain.save()
            self.addCleanup(domain.delete)
            return domain._id

        names = ['b', 'a', 'c']
        expected_ids = {name: _create_domain(name) for name in names}

        ids = get_domain_ids_by_names(names)
        self.assertEqual(ids, expected_ids)

    def test_deleted_domain_exists(self):
        x = Domain(name='x')
        x.save()
        y = Domain(name='y')
        y.save()
        y.delete(leave_tombstone=True)
        self.addCleanup(x.delete)
        self.addCleanup(y.delete)
        self.assertTrue(domain_exists('x'))
        self.assertFalse(deleted_domain_exists('x'))
        self.assertTrue(domain_or_deleted_domain_exists('x'))

        self.assertFalse(domain_exists('y'))
        self.assertTrue(deleted_domain_exists('y'))
        self.assertTrue(domain_or_deleted_domain_exists('y'))

        self.assertTrue(len(list(iter_all_domains_and_deleted_domains_with_name('x'))), 1)
        self.assertTrue(len(list(iter_all_domains_and_deleted_domains_with_name('y'))), 1)
