from dataclasses import dataclass

from django.test import SimpleTestCase, TestCase

from nose.tools import assert_equal

from casexml.apps.case.mock import CaseFactory, CaseIndex, CaseStructure
from casexml.apps.case.tests.util import (
    delete_all_cases,
    extract_caseblocks_from_xml,
)
from casexml.apps.case.xml import V2
from casexml.apps.phone.restore import (
    RestoreConfig,
    RestoreParams,
    RestoreState,
)

from corehq.apps.accounting.models import SoftwarePlanEdition
from corehq.apps.accounting.tests.utils import DomainSubscriptionMixin
from corehq.apps.domain.models import Domain
from corehq.apps.users.models import CommCareUser
from corehq.const import LOADTEST_HARD_LIMIT

DOMAIN = 'foo-domain'


class LoadtestUserTest(TestCase, DomainSubscriptionMixin):

    @classmethod
    def setUpClass(cls):
        super(LoadtestUserTest, cls).setUpClass()
        cls.domain = Domain.get_or_create_with_name(DOMAIN)
        cls.setup_subscription(DOMAIN, SoftwarePlanEdition.PRO)

    def setUp(self):
        self.user = CommCareUser.create(
            DOMAIN, 'somebody', 'password',
            created_by=None, created_via=None,
        )
        self.factory = CaseFactory(
            domain=DOMAIN,
            case_defaults={'owner_id': self.user._id},
        )

    def tearDown(self):
        self.user.delete(DOMAIN, deleted_by=None)
        delete_all_cases()

    @classmethod
    def tearDownClass(cls):
        cls.domain.delete()
        super(LoadtestUserTest, cls).tearDownClass()

    def test_no_factor_set(self):
        self.user.loadtest_factor = None
        self.user.save()
        case = self.factory.create_case()
        restore_config = RestoreConfig(
            project=self.domain,
            restore_user=self.user.to_ota_restore_user(self.domain.name),
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
            restore_user=self.user.to_ota_restore_user(self.domain.name),
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
            restore_user=self.user.to_ota_restore_user(self.domain.name),
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


class TestGetSafeLoadtestFactor(SimpleTestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        project = Domain(name=DOMAIN)
        restore_user = FakeRestoreUser(loadtest_factor=1000)
        cls.restore_state = RestoreState(
            project=project,
            restore_user=restore_user,
            params=None,
        )

    def test_get_safe_loadtest_factor_safe(self):
        safe = self.restore_state.get_safe_loadtest_factor(total_cases=10)
        assert_equal(safe, 1000)

    def test_get_safe_loadtest_factor_unsafe(self):
        safe = self.restore_state.get_safe_loadtest_factor(total_cases=1000)
        assert_equal(safe, 500)

    def test_get_safe_loadtest_factor_above_limit(self):
        too_many = LOADTEST_HARD_LIMIT + 1
        safe = self.restore_state.get_safe_loadtest_factor(total_cases=too_many)
        assert_equal(safe, 1)


@dataclass
class FakeRestoreUser:
    loadtest_factor: int
