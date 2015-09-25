from corehq.dbaccessors.couchapps.all_docs import \
    get_all_doc_ids_for_domain_grouped_by_db, get_doc_count_by_type
from dimagi.utils.couch.database import get_db
from django.test import TestCase


class AllDocsTest(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.domain = 'all-docs-domain'
        cls.main_db_doc = {'_id': 'main_db_doc', 'domain': cls.domain,
                           'doc_type': 'Application'}
        cls.users_db_doc = {'_id': 'users_db_doc', 'domain': cls.domain,
                            'doc_type': 'CommCareUser'}
        get_db(None).save_doc(cls.main_db_doc)
        get_db('users').save_doc(cls.users_db_doc)

    @classmethod
    def tearDownClass(cls):
        get_db(None).delete_doc(cls.main_db_doc)
        get_db('users').delete_doc(cls.users_db_doc)

    def test_get_all_doc_ids_for_domain_grouped_by_db(self):
        self.assertEqual(
            {key.uri: list(value) for key, value in
             get_all_doc_ids_for_domain_grouped_by_db(self.domain)},
            {get_db(None).uri: ['main_db_doc'],
             get_db('users').uri: ['users_db_doc']}
        )

    def test_get_doc_count_by_type(self):
        self.assertEqual(get_doc_count_by_type(get_db(None), 'Application'), 1)
        self.assertEqual(get_doc_count_by_type(get_db('users'), 'CommCareUser'), 1)
        self.assertEqual(get_doc_count_by_type(get_db(None), 'CommCareUser'), 0)
        self.assertEqual(get_doc_count_by_type(get_db('users'), 'Application'), 0)
