from django.test import TestCase
from casexml.apps.case.models import CommCareCase
from corehq.apps.casegroups.dbaccessors import get_case_groups_in_domain, \
    get_number_of_case_groups_in_domain, get_case_group_meta_in_domain
from corehq.apps.casegroups.models import CommCareCaseGroup


class DBAccessorsTest(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.domain = 'skbanskdjoasdkng'
        cls.cases = [
            CommCareCase(name='A', domain=cls.domain),
            CommCareCase(name='B', domain=cls.domain),
            CommCareCase(name='C', domain=cls.domain),
            CommCareCase(name='D', domain=cls.domain),
            CommCareCase(name='X', domain='bunny'),
        ]
        CommCareCase.get_db().bulk_save(cls.cases)
        cls.case_groups = [
            CommCareCaseGroup(name='alpha', domain=cls.domain,
                              cases=[cls.cases[0]._id, cls.cases[1]._id]),
            CommCareCaseGroup(name='beta', domain=cls.domain,
                              cases=[cls.cases[2]._id, cls.cases[3]._id]),
            CommCareCaseGroup(name='gamma', domain=cls.domain,
                              cases=[cls.cases[0]._id, cls.cases[3]._id]),
            CommCareCaseGroup(name='delta', domain=cls.domain,
                              cases=[cls.cases[1]._id, cls.cases[2]._id]),
        ]
        CommCareCaseGroup.get_db().bulk_save(cls.case_groups)

    @classmethod
    def tearDownClass(cls):
        CommCareCase.get_db().bulk_delete(cls.cases)
        CommCareCaseGroup.get_db().bulk_delete(cls.case_groups)

    def assert_doc_lists_equal(self, docs1, docs2):
        self.assertEqual(
            sorted([(doc._id, doc.to_json()) for doc in docs1]),
            sorted([(doc._id, doc.to_json()) for doc in docs2]),
        )

    def test_get_case_groups_in_domain(self):
        self.assert_doc_lists_equal(
            get_case_groups_in_domain(self.domain),
            self.case_groups,
        )

    def test_get_number_of_case_groups_in_domain(self):
        self.assertEqual(
            get_number_of_case_groups_in_domain(self.domain),
            len(self.case_groups)
        )

    def test_get_case_group_meta_in_domain(self):
        self.assertEqual(
            get_case_group_meta_in_domain(self.domain),
            sorted([(g._id, g.name) for g in self.case_groups],
                   key=lambda (_, name): name)
        )
