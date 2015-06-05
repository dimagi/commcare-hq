from django.test import TestCase
from casexml.apps.case.dbaccessors import get_open_case_docs_by_type
from casexml.apps.case.models import CommCareCase
from corehq.apps.hqcase.dbaccessors import get_number_of_cases_in_domain, \
    get_case_ids_in_domain


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

    def test_get_open_case_docs_by_type(self):
        # this is actually in case/all_cases, but testing here
        self.assertEqual(
            sorted(get_open_case_docs_by_type(self.domain, 'type1'),
                   key=lambda doc: doc['_id']),
            sorted([case.to_json() for case in self.cases
                    if case.domain == self.domain and case.type == 'type1'
                    and not case.closed],
                   key=lambda doc: doc['_id'])
        )

    def test_get_open_case_docs_by_type__owner_id(self):
        # this is actually in case/all_cases, but testing here
        self.assertEqual(
            sorted(get_open_case_docs_by_type(self.domain, 'type1',
                                              owner_id='XXX'),
                   key=lambda doc: doc['_id']),
            sorted([case.to_json() for case in self.cases
                    if case.domain == self.domain and case.type == 'type1'
                    and not case.closed and case.user_id == 'XXX'],
                   key=lambda doc: doc['_id'])
        )
