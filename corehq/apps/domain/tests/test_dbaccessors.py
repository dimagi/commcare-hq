from __future__ import absolute_import
from __future__ import unicode_literals
import functools
import uuid
import datetime
from django.test import TestCase
from casexml.apps.case.models import CommCareCase
from corehq.apps.commtrack.models import CommtrackConfig
from corehq.apps.domain.dbaccessors import (
    count_downloads_for_all_snapshots,
    get_doc_count_in_domain_by_class,
    get_doc_ids_in_domain_by_class,
    get_docs_in_domain_by_class,
    get_domain_ids_by_names,
)
from corehq.apps.domain.models import Domain
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.groups.models import Group
from corehq.apps.users.models import UserRole
from couchforms.models import XFormInstance
from corehq.apps.domain.dbaccessors import get_doc_ids_in_domain_by_type, iterate_doc_ids_in_domain_by_type
from dimagi.utils.couch.database import get_db


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

    def test_count_downloads_for_all_snapshots(self):
        counts = [5, 12, 10]
        for count in counts:
            copy = self.project.save_snapshot(share_reminders=False, copy_by_id=set())
            copy.downloads = count
            copy.save()
        self.assertEqual(
            count_downloads_for_all_snapshots(self.project.get_id), sum(counts))
