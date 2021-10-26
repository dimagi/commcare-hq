import itertools
import uuid

from django.test import TestCase

from corehq.form_processor.backends.sql.dbaccessors import doc_type_to_state
from corehq.form_processor.tests.utils import create_form_for_test, FormProcessorTestUtils
from pillowtop.reindexer.change_providers.form import SqlDomainXFormChangeProvider


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
