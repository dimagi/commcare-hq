from django.test import TestCase

from casexml.apps.case.mock import CaseFactory, CaseIndex, CaseStructure
from casexml.apps.case.tests.util import (
    delete_all_cases,
    extract_caseblocks_from_xml,
)
from casexml.apps.case.xml import V2
from casexml.apps.phone.models import loadtest_users_enabled
from casexml.apps.phone.restore import RestoreConfig, RestoreParams

from corehq.apps.accounting.models import SoftwarePlanEdition
from corehq.apps.accounting.tests.utils import DomainSubscriptionMixin
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.users.models import CommCareUser

DOMAIN = 'foo-domain'


class LoadtestUserTest(TestCase, DomainSubscriptionMixin):

    @classmethod
    def setUpClass(cls):
        super(LoadtestUserTest, cls).setUpClass()
        cls.domain = create_domain(DOMAIN)
        cls.setup_subscription(DOMAIN, SoftwarePlanEdition.PRO)
        cls.user = CommCareUser.create(
            DOMAIN, 'somebody', 'password',
            created_by=None, created_via=None,
        )
        cls.factory = CaseFactory(
            domain=DOMAIN,
            case_defaults={'owner_id': cls.user._id},
        )

    def setUp(self):
        delete_all_cases()

    @classmethod
    def tearDownClass(cls):
        cls.user.delete(DOMAIN, deleted_by=None)
        cls.domain.delete()
        super(LoadtestUserTest, cls).tearDownClass()

    def test_loadtest_users_enabled(self):
        self.assertTrue(loadtest_users_enabled(DOMAIN))

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
        self.assertEqual(1, len([cb for cb in caseblocks
                                 if cb.get_case_id() == case1.case_id]))
        self.assertEqual(1, len([cb for cb in caseblocks
                                 if cb.get_case_id() == case2.case_id]))
        self.assertEqual(3, len([cb for cb in caseblocks
                                 if case1.name in cb.get_case_name()]))
        self.assertEqual(3, len([cb for cb in caseblocks
                                 if case2.name in cb.get_case_name()]))

    def test_parent_child(self):
        self.user.loadtest_factor = 3
        self.user.save()
        child, parent = self.factory.create_or_update_case(
            CaseStructure(
                attrs={'case_name': 'parent', 'create': True},
                indices=[CaseIndex(CaseStructure(
                    attrs={'case_name': 'child', 'create': True}))],
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
        self.assertEqual(1, len([cb for cb in caseblocks
                                 if cb.get_case_id() == child.case_id]))
        self.assertEqual(1, len([cb for cb in caseblocks
                                 if cb.get_case_id() == parent.case_id]))
        self.assertEqual(3, len([cb for cb in caseblocks
                                 if child.name in cb.get_case_name()]))
        self.assertEqual(3, len([cb for cb in caseblocks
                                 if parent.name in cb.get_case_name()]))
