from django.test import TestCase
from casexml.apps.case.models import CommCareCase
from corehq.apps.hqcase.dbaccessors import get_number_of_cases_in_domain, \
    get_case_ids_in_domain


class DBAccessorsTest(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.domain = 'lalksdjflakjsdf'
        cls.cases = [
            CommCareCase(domain=cls.domain, type='type1', name='Alice'),
            CommCareCase(domain=cls.domain, type='type2', name='Bob'),
            CommCareCase(domain=cls.domain, type='type1', name='Candice'),
            CommCareCase(domain=cls.domain, type='type1', name='Derek'),
            CommCareCase(domain='maleficent', type='type1', name='Mallory')
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
