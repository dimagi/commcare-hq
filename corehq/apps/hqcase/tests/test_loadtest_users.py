from django.test import TestCase
from casexml.apps.case.mock import CaseFactory, CaseStructure, CaseIndex
from casexml.apps.case.tests.util import delete_all_cases
from casexml.apps.case.tests.util import extract_caseblocks_from_xml
from casexml.apps.case.xml import V2
from casexml.apps.phone.restore import RestoreConfig, RestoreParams
from corehq.apps.domain.models import Domain
from corehq.apps.users.models import CommCareUser
from corehq.form_processor.tests.utils import conditionally_run_with_all_backends
from corehq.toggles import ENABLE_LOADTEST_USERS


class LoadtestUserTest(TestCase):

    @classmethod
    def setUpClass(cls):
        cls.domain = Domain(name='foo')
        cls.domain.save()
        cls.user = CommCareUser.create(cls.domain.name, 'somebody', 'password')
        cls.user_id = cls.user._id
        cls.factory = CaseFactory(domain='foo', case_defaults={'owner_id': cls.user_id})
        ENABLE_LOADTEST_USERS.set('foo', True, namespace='domain')

    def setUp(self):
        delete_all_cases()
        self.assertTrue(ENABLE_LOADTEST_USERS.enabled('foo'))

    @classmethod
    def tearDownClass(cls):
        cls.user.delete()
        cls.domain.delete()

    @conditionally_run_with_all_backends
    def test_no_factor_set(self):
        self.user.loadtest_factor = None
        self.user.save()
        case = self.factory.create_case()
        restore_config = RestoreConfig(
            project=self.domain,
            restore_user=self.user.to_ota_restore_user(),
            params=RestoreParams(version=V2)
        )
        payload_string = restore_config.get_payload().as_string()
        caseblocks = extract_caseblocks_from_xml(payload_string)
        self.assertEqual(1, len(caseblocks))
        self.assertEqual(caseblocks[0].get_case_id(), case.case_id)

    @conditionally_run_with_all_backends
    def test_simple_factor(self):
        self.user.loadtest_factor = 3
        self.user.save()
        case1 = self.factory.create_case(case_name='case1')
        case2 = self.factory.create_case(case_name='case2')
        restore_config = RestoreConfig(
            project=self.domain,
            restore_user=self.user.to_ota_restore_user(),
            params=RestoreParams(version=V2),
        )
        payload_string = restore_config.get_payload().as_string()
        caseblocks = extract_caseblocks_from_xml(payload_string)
        self.assertEqual(6, len(caseblocks))
        self.assertEqual(1, len(filter(lambda cb: cb.get_case_id() == case1.case_id, caseblocks)))
        self.assertEqual(1, len(filter(lambda cb: cb.get_case_id() == case2.case_id, caseblocks)))
        self.assertEqual(3, len(filter(lambda cb: case1.name in cb.get_case_name(), caseblocks)))
        self.assertEqual(3, len(filter(lambda cb: case2.name in cb.get_case_name(), caseblocks)))

    @conditionally_run_with_all_backends
    def test_parent_child(self):
        self.user.loadtest_factor = 3
        self.user.save()
        child, parent = self.factory.create_or_update_case(
            CaseStructure(
                attrs={'case_name': 'parent', 'create': True},
                indices=[
                    CaseIndex(CaseStructure(attrs={'case_name': 'child', 'create': True})),
                ]
            )
        )
        restore_config = RestoreConfig(
            project=self.domain,
            restore_user=self.user.to_ota_restore_user(),
            params=RestoreParams(version=V2)
        )
        payload_string = restore_config.get_payload().as_string()
        caseblocks = extract_caseblocks_from_xml(payload_string)
        self.assertEqual(6, len(caseblocks))
        self.assertEqual(1, len(filter(lambda cb: cb.get_case_id() == child.case_id, caseblocks)))
        self.assertEqual(1, len(filter(lambda cb: cb.get_case_id() == parent.case_id, caseblocks)))
        self.assertEqual(3, len(filter(lambda cb: child.name in cb.get_case_name(), caseblocks)))
        self.assertEqual(3, len(filter(lambda cb: parent.name in cb.get_case_name(), caseblocks)))
