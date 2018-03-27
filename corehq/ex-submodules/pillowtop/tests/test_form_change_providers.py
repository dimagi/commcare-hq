from __future__ import absolute_import
from __future__ import unicode_literals
import itertools
import uuid

from django.test import SimpleTestCase, TestCase
from fakecouch import FakeCouchDb

from corehq.form_processor.backends.sql.dbaccessors import doc_type_to_state
from corehq.form_processor.tests.utils import create_form_for_test, FormProcessorTestUtils
from couchforms.models import XFormInstance, all_known_formlike_doc_types
from pillowtop.reindexer.change_providers.couch import CouchDomainDocTypeChangeProvider
from pillowtop.reindexer.change_providers.form import SqlDomainXFormChangeProvider
from six.moves import range


class TestCouchDomainFormChangeProvider(SimpleTestCase):
    @staticmethod
    def _get_row(doc_id, domain, doc_type):
        return {
            'id': doc_id,
            'key': [domain, doc_type, None], 'value': None, 'doc': {'_id': doc_id, 'doc_type': doc_type}
        }

    @classmethod
    def setUpClass(cls):
        super(TestCouchDomainFormChangeProvider, cls).setUpClass()
        cls.domains = ['d1', 'd2', 'd3']
        cls.form_ids = {
            (domain, doc_type): ['{}-{}-{}'.format(doc_type, domain, i) for i in range(3)]
            for domain in cls.domains
            for doc_type in ['XFormInstance', 'XFormArchived']
        }
        cls.couch_db = FakeCouchDb(views={
            "by_domain_doc_type_date/view":
            [
                (
                    {
                        'startkey': list(domain_doc_type),
                        'endkey': list(domain_doc_type) + [{}],
                        'include_docs': True,
                        'limit': 1000,
                        'reduce': False
                    },
                    [cls._get_row(form_id, domain_doc_type[0], domain_doc_type[1]) for form_id in form_ids]
                )
                for domain_doc_type, form_ids in cls.form_ids.items()
            ]
        })
        XFormInstance.set_db(cls.couch_db)

    def test_change_provider(self):
        provider = CouchDomainDocTypeChangeProvider(
            couch_db=XFormInstance.get_db(),
            domains=self.domains,
            doc_types=all_known_formlike_doc_types()
        )
        doc_ids = {change.id for change in provider.iter_all_changes()}
        self.assertEqual(doc_ids, set(itertools.chain(*list(self.form_ids.values()))))

    def test_change_provider_empty(self):
        provider = CouchDomainDocTypeChangeProvider(
            couch_db=XFormInstance.get_db(),
            domains=[],
            doc_types=all_known_formlike_doc_types()
        )
        self.assertEqual([], [change for change in provider.iter_all_changes()])


class TestSqlDomainFormChangeProvider(TestCase):
    @staticmethod
    def _create_form(domain, doc_type):
        form = create_form_for_test(domain, state=doc_type_to_state[doc_type])
        return form.form_id

    @classmethod
    def setUpClass(cls):
        super(TestSqlDomainFormChangeProvider, cls).setUpClass()
        cls.domains = [uuid.uuid4().hex for i in range(3)]
        cls.form_ids = {
            (domain, doc_type): [cls._create_form(domain, doc_type) for i in range(3)]
            for domain in cls.domains
            for doc_type in ['XFormInstance', 'XFormArchived']
        }

    @classmethod
    def tearDownClass(cls):
        for domain in cls.domains:
            FormProcessorTestUtils.delete_all_sql_forms(domain)
        super(TestSqlDomainFormChangeProvider, cls).tearDownClass()

    def test_change_provider(self):
        provider = SqlDomainXFormChangeProvider(self.domains, chunk_size=2)
        doc_ids = {change.id for change in provider.iter_all_changes()}
        self.assertEqual(doc_ids, set(itertools.chain(*list(self.form_ids.values()))))

    def test_change_provider_empty(self):
        provider = SqlDomainXFormChangeProvider([])
        self.assertEqual([], [change for change in provider.iter_all_changes()])
