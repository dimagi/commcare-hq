from django.test import TestCase

from casexml.apps.case.mock import CaseFactory

from corehq.apps.app_manager.const import USERCASE_TYPE
from corehq.apps.domain.models import Domain
from corehq.apps.users.models import CommCareUser, WebUser
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors


class UsercaseAccessorsTests(TestCase):

    @classmethod
    def setUpClass(cls):
        super(UsercaseAccessorsTests, cls).setUpClass()
        cls.domain = Domain(name='foo')
        cls.domain.save()
        cls.user = CommCareUser.create(cls.domain.name, 'username', 's3cr3t', None, None)
        cls.accessor = CaseAccessors(cls.domain.name)

    @classmethod
    def tearDownClass(cls):
        cls.user.delete(cls.domain.name, deleted_by=None)
        cls.domain.delete()
        super(UsercaseAccessorsTests, cls).tearDownClass()

    def setUp(self):
        factory = CaseFactory(domain='foo')
        factory.create_case(case_type=USERCASE_TYPE, owner_id=self.user._id, case_name='bar',
                            update={'hq_user_id': self.user._id})

    def test_get_usercase(self):
        usercase = self.accessor.get_case_by_domain_hq_user_id(self.user._id, USERCASE_TYPE)
        self.assertIsNotNone(usercase)
        self.assertEqual(usercase.name, 'bar')
