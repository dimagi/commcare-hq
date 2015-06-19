from django.test import TestCase
from casexml.apps.case.dbaccessors import get_open_case_docs_in_domain, \
    get_open_case_ids_in_domain, get_number_of_cases_by_filters
from casexml.apps.case.models import CommCareCase
from corehq.apps.hqcase.dbaccessors import get_number_of_cases_in_domain, \
    get_case_ids_in_domain, get_case_types_for_domain, get_cases_in_domain, \
    get_case_ids_in_domain_by_owner, get_number_of_cases_in_domain_by_owner


class DBAccessorsTest(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.domain = 'lalksdjflakjsdf'
        cls.cases = [
            CommCareCase(domain=cls.domain, type='type1', name='Alice', user_id='XXX'),
            CommCareCase(domain=cls.domain, type='type2', name='Bob', user_id='XXX'),
            CommCareCase(domain=cls.domain, type='type1', name='Candice', user_id='ZZZ'),
            CommCareCase(domain=cls.domain, type='type1', name='Derek', user_id='XXX', closed=True),
            CommCareCase(domain='maleficent', type='type1', name='Mallory', user_id='YYY')
        ]
        CommCareCase.get_db().bulk_save(cls.cases)

    @classmethod
    def tearDownClass(cls):
        CommCareCase.get_db().bulk_delete(cls.cases)

    def test_get_number_of_cases_in_domain(self):
        self.assertEqual(
            get_number_of_cases_in_domain(self.domain),
            len([case for case in self.cases if case.domain == self.domain])
        )

    def test_get_number_of_cases_in_domain__type(self):
        self.assertEqual(
            get_number_of_cases_in_domain(self.domain, type='type1'),
            len([case for case in self.cases
                 if case.domain == self.domain and case.type == 'type1'])
        )

    def test_get_case_ids_in_domain(self):
        self.assertEqual(
            set(get_case_ids_in_domain(self.domain)),
            {case.get_id for case in self.cases if case.domain == self.domain}
        )

    def test_get_case_ids_in_domain__type(self):
        self.assertEqual(
            set(get_case_ids_in_domain(self.domain, type='type1')),
            {case.get_id for case in self.cases
             if case.domain == self.domain and case.type == 'type1'}
        )

    def assert_doc_list_equal(self, doc_list_1, doc_list_2, raw_json=False):
        if not raw_json:
            doc_list_1 = [doc.to_json() for doc in doc_list_1]
            doc_list_2 = [doc.to_json() for doc in doc_list_2]
        doc_list_1 = sorted(doc_list_1, key=lambda doc: doc['_id'])
        doc_list_2 = sorted(doc_list_2, key=lambda doc: doc['_id'])
        self.assertEqual(doc_list_1, doc_list_2)

    def test_get_cases_in_domain(self):
        self.assert_doc_list_equal(
            get_cases_in_domain(self.domain),
            [case for case in self.cases if case.domain == self.domain]
        )

    def test_get_cases_in_domain__type(self):
        self.assert_doc_list_equal(
            get_cases_in_domain(self.domain, type='type1'),
            [case for case in self.cases
             if case.domain == self.domain and case.type == 'type1'],
        )

    def test_get_open_case_ids_in_domain(self):
        # this is actually in the 'case' app, but testing here
        self.assertEqual(
            set(get_open_case_ids_in_domain(self.domain, 'type1')),
            {case.get_id for case in self.cases
             if case.domain == self.domain and case.type == 'type1'
                and not case.closed},
        )

    def test_get_open_case_ids_in_domain__owner_id(self):
        # this is actually in the 'case' app, but testing here
        self.assertEqual(
            set(get_open_case_ids_in_domain(self.domain, 'type1', owner_id='XXX')),
            {case.get_id for case in self.cases
             if case.domain == self.domain and case.type == 'type1'
                and not case.closed and case.user_id == 'XXX'},
        )
        self.assertEqual(
            set(get_open_case_ids_in_domain(self.domain, owner_id='XXX')),
            {case.get_id for case in self.cases
             if case.domain == self.domain
                and not case.closed and case.user_id == 'XXX'},
        )

    def test_get_open_case_docs_by_type(self):
        # this is actually in the 'case' app, but testing here
        self.assert_doc_list_equal(
            get_open_case_docs_in_domain(self.domain, 'type1'),
            [case.to_json() for case in self.cases
             if case.domain == self.domain and case.type == 'type1'
                and not case.closed],
            raw_json=True
        )

    def test_get_open_case_docs_by_type__owner_id(self):
        # this is actually in the 'case' app, but testing here
        self.assert_doc_list_equal(
            get_open_case_docs_in_domain(self.domain, 'type1', owner_id='XXX'),
            [case.to_json() for case in self.cases
             if case.domain == self.domain and case.type == 'type1'
                and not case.closed and case.user_id == 'XXX'],
            raw_json=True
        )

    def test_get_case_types_for_domain(self):
        self.assertEqual(
            set(get_case_types_for_domain(self.domain)),
            {case.type for case in self.cases if case.domain == self.domain}
        )

    def test_get_cases_by_owner_type_status_date(self):
        # this is actually in the 'case' app, but testing here
        result = get_number_of_cases_by_filters(
            self.domain, 'XXX', case_type=None,
            status=None, date_range=None)

        self.assertEqual(
            result,
            len([case for case in self.cases
                 if case.domain == self.domain and case.user_id == 'XXX'])
        )

    def test_get_case_ids_in_domain_by_owner(self):
        self.assertEqual(
            set(get_case_ids_in_domain_by_owner(self.domain, owner_id='XXX')),
            {case.get_id for case in self.cases
             if case.domain == self.domain and case.user_id == 'XXX'}
        )
        self.assertEqual(
            set(get_case_ids_in_domain_by_owner(
                self.domain, owner_id__in=['XXX'])),
            {case.get_id for case in self.cases
             if case.domain == self.domain and case.user_id == 'XXX'}
        )
        self.assertEqual(
            set(get_case_ids_in_domain_by_owner(self.domain, owner_id='XXX',
                                                closed=False)),
            {case.get_id for case in self.cases
             if case.domain == self.domain and case.user_id == 'XXX'
                and case.closed is False}
        )
        self.assertEqual(
            set(get_case_ids_in_domain_by_owner(self.domain, owner_id='XXX',
                                                closed=True)),
            {case.get_id for case in self.cases
             if case.domain == self.domain and case.user_id == 'XXX'
                and case.closed is True}
        )

    def test_get_number_of_cases_in_domain_by_owner(self):
        self.assertEqual(
            get_number_of_cases_in_domain_by_owner(self.domain, owner_id='XXX'),
            len([case for case in self.cases
                 if case.domain == self.domain and case.user_id == 'XXX'])
        )
