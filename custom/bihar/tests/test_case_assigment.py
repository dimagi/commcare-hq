from __future__ import absolute_import
import uuid

from django.test import TestCase

from casexml.apps.case.mock import CaseBlock
from casexml.apps.case.tests.util import delete_all_xforms, delete_all_cases
from casexml.apps.case.util import post_case_blocks
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.groups.models import Group
from corehq.apps.users.models import CommCareUser
from corehq.apps.users.util import format_username
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors, FormAccessors
from custom.bihar.exceptions import CaseAssignmentError
from custom.bihar.utils import assign_case


class CaseAssignmentTest(TestCase):
    domain = "case-assignment-test"

    def setUp(self):
        create_domain(self.domain)
        self.primary_user = CommCareUser.create(self.domain, format_username('case-assignment-user', self.domain), "****")
        self.original_owner = CommCareUser.create(self.domain, format_username('original-owner', self.domain), "****")

    def tearDown(self):
        delete_all_cases()
        delete_all_xforms()
        self.primary_user.delete()
        self.original_owner.delete()

    def test_assign_to_unknown_user(self):
        case = self._new_case()
        try:
            assign_case(case.case_id, 'noonehere')
            self.fail('reassigning to nonexistent user should fail')
        except CaseAssignmentError:
            pass

    def test_assign_to_user_in_different_domain(self):
        other_user = CommCareUser.create('bad-domain', format_username('bad-domain-user', self.domain), "****")
        case = self._new_case()
        try:
            assign_case(case.case_id, other_user._id)
            self.fail('reassigning to user in wrong domain should fail')
        except CaseAssignmentError:
            pass

    def test_assign_no_related(self):
        self._make_tree()
        assign_case(self.primary.case_id, self.primary_user._id, include_subcases=False, include_parent_cases=False)
        self._check_state(new_owner_id=self.primary_user._id, expected_changed=[self.primary])

    def test_assign_subcases(self):
        self._make_tree()
        assign_case(self.primary.case_id, self.primary_user._id, include_subcases=True, include_parent_cases=False)
        self._check_state(new_owner_id=self.primary_user._id,
                          expected_changed=[self.primary, self.son, self.daughter,
                                            self.grandson, self.granddaughter, self.grandson2])

    def test_assign_parent_cases(self):
        self._make_tree()
        assign_case(self.primary.case_id, self.primary_user._id, include_subcases=False, include_parent_cases=True)
        self._check_state(new_owner_id=self.primary_user._id,
                          expected_changed=[self.grandfather, self.grandmother, self.parent, self.primary])

    def test_assign_all_related(self):
        self._make_tree()
        assign_case(self.primary.case_id, self.primary_user._id, include_subcases=True, include_parent_cases=True)
        self._check_state(new_owner_id=self.primary_user._id,
                          expected_changed=self.all)

    def test_assign_add_property(self):
        self._make_tree()
        update = {'reassigned': 'yes'}
        assign_case(self.primary.case_id, self.primary_user._id, include_subcases=True, include_parent_cases=True,
                    update=update)
        self._check_state(new_owner_id=self.primary_user._id,
                          expected_changed=self.all, update=update)

    def test_assign_to_group(self):
        group = Group(users=[], name='case-assignment-group', domain=self.domain)
        group.save()
        self._make_tree()
        assign_case(self.primary.case_id, group._id, include_subcases=True, include_parent_cases=True)
        self._check_state(new_owner_id=group._id, expected_changed=self.all)

    def test_assign_noop(self):
        self._make_tree()
        num_forms = len(FormAccessors(self.domain).get_forms_by_type('XFormInstance', limit=1000))
        self.assertTrue(num_forms < 1000)
        res = assign_case(self.primary.case_id, self.original_owner._id, include_subcases=True, include_parent_cases=True)
        self.assertEqual(0, len(res))
        new_num_forms = len(FormAccessors(self.domain).get_forms_by_type('XFormInstance', limit=1000))
        self.assertEqual(new_num_forms, num_forms)

    def test_assign_exclusion(self):
        self._make_tree()
        exclude_fn = lambda case: case._id in (self.grandfather._id, self.primary._id, self.grandson._id)
        assign_case(self.primary.case_id, self.primary_user._id, include_subcases=True, include_parent_cases=True,
                    exclude_function=exclude_fn)
        self._check_state(new_owner_id=self.primary_user._id, expected_changed=[
            self.grandmother, self.parent, self.son, self.daughter, self.granddaughter, self.grandson2
        ])

    def test_assign_bad_index_ref(self):
        # the case has to exist to create the index, but if we delete it later the assignment
        # shouldn't fail
        case = self._new_case()
        case_with_bad_ref = self._new_case(index={'parent': ('person', case._id)})
        case.soft_delete()
        # this call previously failed
        res = assign_case(case_with_bad_ref.case_id, self.primary_user._id,
                          include_subcases=True, include_parent_cases=True)
        self.assertEqual(2, len(res))
        self.assertIn(case_with_bad_ref.case_id, res)
        self.assertIn(case._id, res)

    def _make_tree(self):
        # create a tree that looks like this:
        #      grandmother    grandfather
        #                parent
        #                primary
        #         son               daughter
        # grandson  granddaughter   grandson2
        self.grandmother = self._new_case()
        self.grandfather = self._new_case()
        self.parent = self._new_case(index={'mom': ('person', self.grandmother._id),
                                            'dad': ('person', self.grandfather._id)})
        self.primary = self._new_case(index={'parent': ('person', self.parent._id)})
        self.son = self._new_case(index={'parent': ('person', self.primary._id)})
        self.daughter = self._new_case(index={'parent': ('person', self.primary._id)})
        self.grandson = self._new_case(index={'parent': ('person', self.son._id)})
        self.granddaughter = self._new_case(index={'parent': ('person', self.son._id)})
        self.grandson2 = self._new_case(index={'parent': ('person', self.daughter._id)})

        self.all = [self.grandmother, self.grandfather, self.parent, self.primary,
                    self.son, self.daughter, self.grandson, self.granddaughter, self.grandson2]
        for case in self.all:
            self.assertEqual(case.owner_id, self.original_owner._id)

    def _check_state(self, new_owner_id, expected_changed, update=None):
        expected_ids = set(c._id for c in expected_changed)
        for case in expected_changed:
            expected = CaseAccessors(self.domain).get_case(case._id)
            self.assertEqual(new_owner_id, expected.owner_id)
            if update:
                for prop, value in update.items():
                    self.assertEqual(getattr(expected, prop), value)
        for case in (c for c in self.all if c._id not in expected_ids):
            remaining = CaseAccessors(self.domain).get_case(case._id)
            self.assertEqual(self.original_owner._id, remaining.owner_id)

    def _new_case(self, index=None):
        index = index or {}
        id = uuid.uuid4().hex
        case_block = CaseBlock(
            create=True,
            case_id=id,
            case_type='person',
            owner_id=self.original_owner._id,
            index=index,
        ).as_xml()
        _, [case] = post_case_blocks([case_block], {'domain': self.domain})
        return case
