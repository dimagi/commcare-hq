import uuid
from xml.etree import cElementTree as ElementTree

from django.test import TestCase, override_settings

from unittest import mock

from casexml.apps.case.mock import (
    CaseBlock,
    CaseFactory,
    CaseIndex,
    CaseStructure,
)
from casexml.apps.case.tests.util import delete_all_cases, delete_all_xforms

from corehq.apps.app_manager.const import USERCASE_TYPE
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.hqcase.utils import submit_case_blocks
from corehq.apps.users.dbaccessors import delete_all_users
from corehq.apps.users.model_log import UserModelAction
from corehq.apps.users.models import CommCareUser, UserHistory
from corehq.apps.users.tasks import remove_indices_from_deleted_cases
from corehq.apps.users.util import SYSTEM_USER_ID
from corehq.form_processor.models import CommCareCase, UserArchivedRebuild, XFormInstance


class RetireUserTestCase(TestCase):

    @classmethod
    def setUpClass(cls):
        super(RetireUserTestCase, cls).setUpClass()
        cls.domain = 'test'
        cls.domain_object = create_domain(cls.domain)
        cls.domain_object.usercase_enabled = True
        cls.domain_object.save()

    @classmethod
    def tearDownClass(cls):
        cls.domain_object.delete()
        super(RetireUserTestCase, cls).tearDownClass()

    def setUp(self):
        super(RetireUserTestCase, self).setUp()
        delete_all_users()
        self.username = "fake-person@test.commcarehq.org"
        self.other_username = 'other-user@test.commcarehq.org'
        self.password = "s3cr3t"

        self.commcare_user = CommCareUser.create(self.domain, self.username, self.password, None, None)
        self.commcare_user.save()

        self.other_user = CommCareUser.create(self.domain, self.other_username, self.password, None, None)
        self.other_user.save()

    def tearDown(self):
        delete_all_users()
        delete_all_cases()
        delete_all_xforms()
        super(RetireUserTestCase, self).tearDown()

    @override_settings(UNIT_TESTING=False)
    def test_retire_missing_deleted_by(self):
        with self.assertRaisesMessage(ValueError, "Missing deleted_by"):
            self.commcare_user.retire(self.domain, deleted_by=None)

    def test_retire(self):
        deleted_via = "Test test"

        self.commcare_user.retire(self.domain, deleted_by=self.other_user, deleted_via=deleted_via)
        user_history = UserHistory.objects.get(user_id=self.commcare_user.get_id,
                                               action=UserModelAction.DELETE.value)
        self.assertEqual(user_history.by_domain, self.domain)
        self.assertEqual(user_history.for_domain, self.domain)
        self.assertEqual(user_history.user_type, "CommCareUser")
        self.assertEqual(user_history.changed_by, self.other_user.get_id)
        self.assertEqual(user_history.changed_via, deleted_via)

    @override_settings(UNIT_TESTING=False)
    def test_unretire_missing_unretired_by(self):
        with self.assertRaisesMessage(ValueError, "Missing unretired_by"):
            self.commcare_user.unretire(self.domain, unretired_by=None)

    def test_unretire_user(self):
        case_ids = [uuid.uuid4().hex, uuid.uuid4().hex, uuid.uuid4().hex]

        caseblocks = []
        for i, case_id in enumerate(case_ids):
            owner_id = self.commcare_user._id

            caseblocks.append(CaseBlock(
                create=True,
                case_id=case_id,
                owner_id=owner_id,
                user_id=owner_id,
            ).as_text())
        xform = submit_case_blocks(caseblocks, self.domain, user_id=owner_id)[0]

        self.commcare_user.retire(self.domain, deleted_by=None)
        cases = CommCareCase.objects.get_cases(case_ids, self.domain)
        self.assertTrue(all([c.is_deleted for c in cases]))
        self.assertEqual(len(cases), 3)
        form = XFormInstance.objects.get_form(xform.form_id, self.domain)
        self.assertTrue(form.is_deleted)

        self.assertEqual(
            UserHistory.objects.filter(
                user_id=self.commcare_user.get_id,
                action=UserModelAction.CREATE.value
            ).count(),
            0
        )
        self.commcare_user.unretire(self.domain, unretired_by=self.other_user, unretired_via="Test")

        user_history = UserHistory.objects.get(
            user_id=self.commcare_user.get_id,
            action=UserModelAction.CREATE.value
        )
        self.assertEqual(user_history.by_domain, self.domain)
        self.assertEqual(user_history.for_domain, self.domain)
        self.assertEqual(user_history.user_type, "CommCareUser")
        self.assertEqual(user_history.changed_by, self.other_user.get_id)
        self.assertEqual(user_history.changed_via, "Test")

        cases = CommCareCase.objects.get_cases(case_ids, self.domain)
        self.assertFalse(all([c.is_deleted for c in cases]))
        self.assertEqual(len(cases), 3)
        form = XFormInstance.objects.get_form(xform.form_id, self.domain)
        self.assertFalse(form.is_deleted)

    def test_undelete_system_forms(self):
        case_ids = [uuid.uuid4().hex, uuid.uuid4().hex, uuid.uuid4().hex]

        # create 3 cases
        caseblocks = []
        for case_id in case_ids:
            owner_id = self.commcare_user._id

            caseblocks.append(CaseBlock(
                create=True,
                case_id=case_id,
                owner_id=owner_id,
                user_id=owner_id,
            ).as_text())
        submit_case_blocks(caseblocks, self.domain, user_id=owner_id)[0]

        # submit a system form to update one, and another to update two
        caseblocks = [
            CaseBlock(
                create=False,
                case_id=case_id,
                user_id=SYSTEM_USER_ID,
                update={'foo': 'bar'},
            ).as_text()
            for case_id in case_ids
        ]
        xform_1 = submit_case_blocks(caseblocks[:1], self.domain, user_id=SYSTEM_USER_ID)[0]
        xform_2 = submit_case_blocks(caseblocks[1:], self.domain, user_id=SYSTEM_USER_ID)[0]

        # Both forms should be deleted on `retire()`
        self.commcare_user.retire(self.domain, deleted_by=None)
        form_1 = XFormInstance.objects.get_form(xform_1.form_id, self.domain)
        self.assertTrue(form_1.is_deleted)
        form_2 = XFormInstance.objects.get_form(xform_2.form_id, self.domain)
        self.assertTrue(form_2.is_deleted)

        # Both forms should be undeleted on `unretire()`
        self.commcare_user.unretire(self.domain, unretired_by=None)
        form_1 = XFormInstance.objects.get_form(xform_1.form_id, self.domain)
        self.assertFalse(form_1.is_deleted)
        form_2 = XFormInstance.objects.get_form(xform_2.form_id, self.domain)
        self.assertFalse(form_2.is_deleted)

    def test_deleted_indices_removed(self):
        factory = CaseFactory(
            self.domain,
            case_defaults={
                'user_id': self.commcare_user._id,
                'owner_id': self.commcare_user._id,
                'case_type': 'a-case',
                'create': True,
            },
        )
        # create a parent/child set of cases
        parent_id, child_id = [uuid.uuid4().hex for i in range(2)]
        child, parent = factory.create_or_update_case(CaseStructure(
            case_id=child_id,
            indices=[
                CaseIndex(CaseStructure(case_id=parent_id))
            ]
        ))
        # confirm the child has an index, and 1 form
        self.assertEqual(1, len(child.indices))
        self.assertEqual(parent_id, child.indices[0].referenced_id)
        self.assertEqual(1, len(child.xform_ids))

        # simulate parent deletion
        CommCareCase.objects.soft_delete_cases(self.domain, [parent_id])

        # call the remove index task
        remove_indices_from_deleted_cases(self.domain, [parent_id])

        # check that the index is removed via a new form
        child = CommCareCase.objects.get_case(child_id, self.domain)
        self.assertEqual(1, len(child.indices))
        self.assertTrue(child.indices[0].is_deleted)
        self.assertEqual(2, len(child.xform_ids))

    @mock.patch("casexml.apps.case.cleanup.rebuild_case_from_forms")
    def test_rebuild_cases_with_new_owner(self, rebuild_case):
        """
            If cases have a different owner to the person who submitted it
            rebuild it when the submitter is retired.
        """

        case_id = uuid.uuid4().hex
        caseblock = CaseBlock(
            create=True,
            case_id=case_id,
            owner_id=self.commcare_user._id,
            user_id=self.commcare_user._id,
        )
        casexml = ElementTree.tostring(caseblock.as_xml(), encoding='utf-8').decode('utf-8')
        submit_case_blocks(casexml, self.domain, user_id=self.other_user._id)

        self.other_user.retire(self.domain, deleted_by=None)

        detail = UserArchivedRebuild(user_id=self.other_user.user_id)
        rebuild_case.assert_called_once_with(self.domain, case_id, detail)

    @mock.patch("casexml.apps.case.cleanup.rebuild_case_from_forms")
    def test_dont_rebuild(self, rebuild_case):
        """ Don't rebuild cases that are owned by other users """

        case_id = uuid.uuid4().hex
        caseblock = CaseBlock(
            create=True,
            case_id=case_id,
            owner_id=self.commcare_user._id,
            user_id=self.commcare_user._id,
        )
        casexml = ElementTree.tostring(caseblock.as_xml(), encoding='utf-8').decode('utf-8')
        submit_case_blocks(casexml, self.domain, user_id=self.commcare_user._id)

        self.other_user.retire(self.domain, deleted_by=None)

        self.assertEqual(rebuild_case.call_count, 0)

    @mock.patch("casexml.apps.case.cleanup.rebuild_case_from_forms")
    def test_multiple_case_blocks_all_rebuilt(self, rebuild_case):
        """ Rebuild all cases in forms with multiple case blocks """

        case_ids = [uuid.uuid4().hex, uuid.uuid4().hex, uuid.uuid4().hex]

        caseblocks = [CaseBlock(
            create=True,
            case_id=case_id,
            owner_id=self.commcare_user._id,
            user_id=self.commcare_user._id,
        ) for case_id in case_ids]
        casexmls = [
            ElementTree.tostring(caseblock.as_xml(), encoding='utf-8').decode('utf-8')
            for caseblock in caseblocks
        ]
        submit_case_blocks(casexmls, self.domain, user_id=self.other_user._id)

        self.other_user.retire(self.domain, deleted_by=None)

        detail = UserArchivedRebuild(user_id=self.other_user.user_id)
        expected_call_args = [mock.call(self.domain, case_id, detail) for case_id in case_ids]

        self.assertEqual(rebuild_case.call_count, len(case_ids))
        self.assertItemsEqual(rebuild_case.call_args_list, expected_call_args)

    @mock.patch("casexml.apps.case.cleanup.rebuild_case_from_forms")
    def test_multiple_case_blocks_some_deleted(self, rebuild_case):
        """ Don't rebuild deleted cases """

        case_ids = [uuid.uuid4().hex, uuid.uuid4().hex, uuid.uuid4().hex]

        for i, case_id in enumerate(case_ids):
            if i == 0:
                # only the first case is owned by the user getting retired
                owner_id = self.other_user._id
            else:
                owner_id = self.commcare_user._id

            caseblock = CaseBlock(
                create=True,
                case_id=case_id,
                owner_id=owner_id,
                user_id=self.commcare_user._id,
            )
            submit_case_blocks(caseblock.as_text(), self.domain, user_id=self.other_user._id)

        self.other_user.retire(self.domain, deleted_by=None)

        detail = UserArchivedRebuild(user_id=self.other_user.user_id)
        expected_call_args = [mock.call(self.domain, case_id, detail) for case_id in case_ids[1:]]

        self.assertEqual(rebuild_case.call_count, len(case_ids) - 1)
        self.assertItemsEqual(rebuild_case.call_args_list, expected_call_args)

    def test_all_case_forms_deleted(self):
        from corehq.apps.callcenter.sync_usercase import sync_usercases
        sync_usercases(self.commcare_user, self.domain)

        usercase_id = self.commcare_user.get_usercase_id()

        # other user submits form against the case (should get deleted)
        caseblock = CaseBlock(
            create=False,
            case_id=usercase_id,
        )
        submit_case_blocks(caseblock.as_text(), self.domain, user_id=self.other_user._id)

        case_ids = CommCareCase.objects.get_case_ids_in_domain_by_owners(
            self.domain, [self.commcare_user._id])
        self.assertEqual(1, len(case_ids))

        form_ids = XFormInstance.objects.get_form_ids_for_user(self.domain, self.commcare_user._id)
        self.assertEqual(0, len(form_ids))

        usercase = self.commcare_user.get_usercase()
        self.assertEqual(2, len(usercase.xform_ids))

        self.commcare_user.retire(self.domain, deleted_by=None)

        for form_id in usercase.xform_ids:
            self.assertTrue(XFormInstance.objects.get_form(form_id, self.domain).is_deleted)

        self.assertFalse(CommCareCase.objects.get_case(usercase_id, self.domain).closed)
        self.assertTrue(CommCareCase.objects.get_case(usercase_id, self.domain).is_deleted)
        self.assertIsNone(CommCareCase.objects.get_case_by_external_id(
            self.domain, self.commcare_user._id, USERCASE_TYPE))

    def test_forms_touching_live_case_not_deleted(self):
        case_id = uuid.uuid4().hex
        caseblock = CaseBlock(
            create=True,
            case_id=case_id,
            owner_id=self.commcare_user._id,
            user_id=self.commcare_user._id,
        )
        xform, _ = submit_case_blocks(caseblock.as_text(), self.domain)

        # other user submits form against the case and another case not owned by the user
        # should NOT get deleted since this form touches a case that's still 'alive'
        double_case_xform, _ = submit_case_blocks([
            CaseBlock(
                create=False,
                case_id=case_id,
            ).as_text(),
            CaseBlock(
                create=True,
                case_id=uuid.uuid4().hex,
                owner_id=self.other_user._id,
                user_id=self.other_user._id,
            ).as_text()
        ], self.domain, user_id=self.other_user._id)

        self.commcare_user.retire(self.domain, deleted_by=None)

        self.assertTrue(XFormInstance.objects.get_form(xform.form_id, self.domain).is_deleted)
        self.assertFalse(XFormInstance.objects.get_form(double_case_xform.form_id, self.domain).is_deleted)

        # When the other user is deleted then the form should get deleted since it no-longer touches
        # any 'live' cases.
        self.other_user.retire(self.domain, deleted_by=None)
        self.assertTrue(XFormInstance.objects.get_form(double_case_xform.form_id, self.domain).is_deleted)
