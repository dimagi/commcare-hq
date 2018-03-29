from __future__ import absolute_import
from __future__ import unicode_literals
from corehq.dbaccessors.couchapps.all_docs import \
    get_all_doc_ids_for_domain_grouped_by_db, get_doc_count_by_type, \
    delete_all_docs_by_doc_type, get_doc_count_by_domain_type
from dimagi.utils.couch.database import get_db
from django.test import TestCase


class AllDocsTest(TestCase):
    maxDiff = None

    @classmethod
    def setUpClass(cls):
        super(AllDocsTest, cls).setUpClass()
        cls.main_db = get_db(None)
        cls.users_db = get_db('users')
        cls.doc_types = ('Application', 'CommCareUser')
        delete_all_docs_by_doc_type(cls.main_db, cls.doc_types)
        delete_all_docs_by_doc_type(cls.users_db, cls.doc_types)
        cls.domain1 = 'all-docs-domain1'
        cls.domain2 = 'all-docs-domain2'
        cls.main_db_doc = {'_id': 'main_db_doc', 'doc_type': 'Application'}
        cls.users_db_doc = {'_id': 'users_db_doc', 'doc_type': 'CommCareUser'}
        for doc_type in cls.doc_types:
            for domain in (cls.domain1, cls.domain2):
                db_alias = 'main' if doc_type == 'Application' else 'users'
                doc_id = '{}_db_doc_{}'.format(db_alias, domain)
                doc = {'_id': doc_id, 'doc_type': doc_type, 'domain': domain}
                if doc_type == 'Application':
                    cls.main_db.save_doc(doc)
                else:
                    cls.users_db.save_doc(doc)

    @classmethod
    def tearDownClass(cls):
        delete_all_docs_by_doc_type(cls.main_db, cls.doc_types)
        delete_all_docs_by_doc_type(cls.users_db, cls.doc_types)
        super(AllDocsTest, cls).tearDownClass()

    def test_get_all_doc_ids_for_domain_grouped_by_db(self):
        self.assertEqual(
            {key.uri: list(value) for key, value in
             get_all_doc_ids_for_domain_grouped_by_db(self.domain1)},
            {get_db(None).uri: ['main_db_doc_all-docs-domain1'],
             get_db('users').uri: ['users_db_doc_all-docs-domain1'],
             get_db('meta').uri: [],
             get_db('fixtures').uri: [],
             get_db('domains').uri: [],
             get_db('apps').uri: []}
        )

    def test_get_doc_count_by_type(self):
        self.assertEqual(get_doc_count_by_type(get_db(None), 'Application'), 2)
        self.assertEqual(get_doc_count_by_type(get_db('users'), 'CommCareUser'), 2)
        self.assertEqual(get_doc_count_by_type(get_db(None), 'CommCareUser'), 0)
        self.assertEqual(get_doc_count_by_type(get_db('users'), 'Application'), 0)

    def test_get_doc_count_by_domain_type(self):
        self.assertEqual(get_doc_count_by_domain_type(get_db(None), self.domain1, 'Application'), 1)
        self.assertEqual(get_doc_count_by_domain_type(get_db(None), self.domain2, 'Application'), 1)
        self.assertEqual(get_doc_count_by_domain_type(get_db(None), 'other', 'Application'), 0)
        self.assertEqual(get_doc_count_by_domain_type(get_db('users'), self.domain1, 'CommCareUser'), 1)
        self.assertEqual(get_doc_count_by_domain_type(get_db('users'), self.domain2, 'CommCareUser'), 1)
        self.assertEqual(get_doc_count_by_domain_type(get_db('users'), 'other', 'CommCareUser'), 0)
        self.assertEqual(get_doc_count_by_domain_type(get_db(None), self.domain1, 'CommCareUser'), 0)
        self.assertEqual(get_doc_count_by_domain_type(get_db('users'), self.domain1, 'Application'), 0)
