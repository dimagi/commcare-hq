from __future__ import absolute_import
from __future__ import unicode_literals
from django.test import TestCase
from casexml.apps.case.mock import CaseFactory
from casexml.apps.case.tests.util import delete_all_cases
from corehq.apps.app_manager.const import USERCASE_TYPE
from corehq.apps.domain.models import Domain
from corehq.apps.hqcase.utils import get_case_by_domain_hq_user_id, get_case_id_by_domain_hq_user_id
from corehq.apps.users.models import CommCareUser


class GetCaseTest(TestCase):

    @classmethod
    def setUpClass(cls):
        super(GetCaseTest, cls).setUpClass()
        cls.domain = Domain(name='foo')
        cls.domain.save()
        cls.user = CommCareUser.create(cls.domain.name, 'username', 's3cr3t')

    @classmethod
    def tearDownClass(cls):
        cls.user.delete()
        super(GetCaseTest, cls).tearDownClass()

    def setUp(self):
        factory = CaseFactory(domain='foo')
        factory.create_case(case_type=USERCASE_TYPE, owner_id=self.user._id, case_name='bar',
                            update={'hq_user_id': self.user._id})

    def tearDown(self):
        delete_all_cases()

    def test_get_usercase(self):
        usercase = get_case_by_domain_hq_user_id(self.domain.name, self.user._id, USERCASE_TYPE)
        self.assertIsNotNone(usercase)
        self.assertEqual(usercase.name, 'bar')

    def test_get_usercase_id(self):
        usercase_id = get_case_id_by_domain_hq_user_id(self.domain.name, self.user._id, USERCASE_TYPE)
        self.assertIsNotNone(usercase_id)
