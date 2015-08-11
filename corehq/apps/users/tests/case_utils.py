from django.test import TestCase
import uuid
from casexml.apps.case.mock import CaseBlock
from casexml.apps.case.models import CommCareCase
from casexml.apps.case.util import post_case_blocks
from casexml.apps.case.xml import V2
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.groups.models import Group
from corehq.apps.users.cases import get_wrapped_owner, get_owning_users, reconcile_ownership, get_owner_id
from corehq.apps.users.models import CommCareUser


class CaseUtilsTestCase(TestCase):

    def setUp(self):
        self.domain = 'test'

    def test_get_wrapped_user(self):
        user = CommCareUser.create(self.domain, 'wrapped-user-test', 'password')
        user.save()
        wrapped = get_wrapped_owner(user._id)
        self.assertTrue(isinstance(wrapped, CommCareUser))

    def test_get_wrapped_group(self):
        group = Group(domain=self.domain, name='wrapped-group-test')
        group.save()
        wrapped = get_wrapped_owner(group._id)
        self.assertTrue(isinstance(wrapped, Group))

    def test_owned_by_user(self):
        user = CommCareUser.create(self.domain, 'owned-user-test', 'password')
        user.save()
        owners = get_owning_users(user._id)
        self.assertEqual(1, len(owners))
        self.assertEqual(owners[0]._id, user._id)
        self.assertTrue(isinstance(owners[0], CommCareUser))

    def test_owned_by_group(self):
        ids = []
        for i in range(5):
            user = CommCareUser.create(self.domain, 'owned-group-test-user-%s' % i, 'password')
            user.save()
            ids.append(user._id)

        group = Group(domain=self.domain, name='owned-group-test-group', users=ids)
        group.save()
        owners = get_owning_users(group._id)
        self.assertEqual(5, len(owners))
        ids_back = []
        for o in owners:
            self.assertTrue(isinstance(o, CommCareUser))
            ids_back.append(o._id)
        self.assertEqual(set(ids), set(ids_back))

class CaseReconciliationTestCase(TestCase):

    def setUp(self):
        self.domain = "test-domain"
        create_domain(self.domain)
        self.user = CommCareUser.create(self.domain, 'reconciliation-test', 'password')
        self.user.save()
        self.other_user = CommCareUser.create(self.domain, 'reconciliation-test-other', 'password')
        self.other_user.save()


    def tearDown(self):
        self.user.delete()
        self.other_user.delete()

    def _make_case(self, user_id, owner_id, **kwargs):
        id = uuid.uuid4().hex
        case_block = CaseBlock(
            create=True,
            case_id=id,
            case_name='Some Name',
            case_type='rectest',
            user_id=user_id,
            owner_id=owner_id,
            version=V2,
            **kwargs
        ).as_xml()
        post_case_blocks([case_block], {'domain': self.domain})
        return CommCareCase.get(id)


    def testNoChange(self):
        # 0. If the case is owned by the user, do nothing.
        case = self._make_case(self.user._id, self.user._id)
        self.assertEqual(case.owner_id, self.user._id)
        reconcile_ownership(case, self.user)
        case = CommCareCase.get(case._id)
        self.assertEqual(case.owner_id, self.user._id)

    def testNoOwner(self):
        # 1. If the case has no owner, make the user the owner.
        case = self._make_case('', '')
        self.assertFalse(case.owner_id)
        reconcile_ownership(case, self.user)
        case = CommCareCase.get(case._id)
        self.assertEqual(case.owner_id, self.user._id)


    def testUserToGroup(self):
        # 2. If the case has an owner that is a user create a new case sharing group,
        # add that user and the new user to the case sharing group make the group the owner.
        case = self._make_case(self.other_user._id, self.other_user._id)
        self.assertEqual(self.other_user._id, case.owner_id)
        reconcile_ownership(case, self.user)
        case = CommCareCase.get(case._id)
        self.assertNotEqual(self.other_user._id, case.owner_id)
        owner = get_wrapped_owner(get_owner_id(case))
        self.assertTrue(isinstance(owner, Group))
        self.assertTrue(self.other_user._id in owner.users)
        self.assertTrue(self.user._id in owner.users)
        self.assertTrue(owner.case_sharing)
        self.assertFalse(owner.reporting)


    def testUserAlreadyInGroup(self):
        # 3. If the case has an owner that is a group, and the user is in the group, do nothing.
        group = Group(
            domain=self.domain,
            name='reconciliation test group',
            users=[self.other_user._id, self.user._id],
            case_sharing=True,
        )
        group.save()
        case = self._make_case(self.other_user._id, group._id)
        self.assertEqual(group._id, case.owner_id)
        reconcile_ownership(case, self.user)
        case = CommCareCase.get(case._id)
        self.assertEqual(group._id, case.owner_id)


    def testUserAddedToGroup(self):
        # 4. If the case has an owner that is a group, and the user is not in the group,
        #    add the user to the group and the leave the owner untouched.
        group = Group(
            domain=self.domain,
            name='reconciliation test group',
            users=[self.other_user._id],
            case_sharing=True,
        )
        group.save()
        case = self._make_case(self.other_user._id, group._id)
        self.assertEqual(group._id, case.owner_id)
        reconcile_ownership(case, self.user)
        case = CommCareCase.get(case._id)
        self.assertEqual(group._id, case.owner_id)
        group = Group.get(group._id)
        self.assertTrue(self.user._id in group.users)


    def testRecursiveUpdates(self):
        parent_case = self._make_case(self.other_user._id, self.other_user._id)
        case = self._make_case(self.other_user._id, self.other_user._id,
                               index={'parent': ('parent-case', parent_case._id)})
        subcase1 = self._make_case(self.other_user._id, self.other_user._id,
                                   index={'parent': ('parent-case', case._id)})
        subcase2 = self._make_case(self.other_user._id, self.other_user._id,
                                   index={'parent': ('parent-case', case._id)})
        subsub1 = self._make_case(self.other_user._id, self.other_user._id,
                                  index={'parent': ('parent-case', subcase1._id)})
        subsub2 = self._make_case(self.other_user._id, self.other_user._id,
                                  index={'parent': ('parent-case', subcase1._id)})
        cases = [case, subcase1, subcase2, subsub1, subsub2]
        for c in cases:
            self.assertEqual(self.other_user._id, c.owner_id)
        reconcile_ownership(case, self.user, recursive=True)
        case = CommCareCase.get(case._id)
        owner = get_wrapped_owner(get_owner_id(case))
        self.assertTrue(isinstance(owner, Group))
        self.assertTrue(self.other_user._id in owner.users)
        self.assertTrue(self.user._id in owner.users)
        self.assertTrue(owner.case_sharing)
        self.assertFalse(owner.reporting)
        for c in cases:
            c = CommCareCase.get(c._id)
            self.assertEqual(owner._id, c.owner_id)

        parent_case = CommCareCase.get(parent_case._id)
        self.assertEqual(self.other_user._id, parent_case.owner_id)
