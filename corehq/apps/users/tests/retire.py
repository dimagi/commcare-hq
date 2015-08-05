from django.test import TestCase
import mock

import uuid
from xml.etree import ElementTree
from corehq.apps.users.models import CommCareUser
from corehq.apps.hqcase.utils import submit_case_blocks
from casexml.apps.case.mock import CaseBlock, CaseFactory, CaseStructure, CaseRelationship
from casexml.apps.case.models import CommCareCase
from casexml.apps.case.tests.util import delete_all_cases, delete_all_xforms
from corehq.apps.users.tasks import remove_indices_from_deleted_cases


class RetireUserTestCase(TestCase):

    def setUp(self):
        self.domain = 'test'
        self.username = "fake-person@test.commcarehq.org"
        self.other_username = 'other-user@test.commcarehq.org'
        self.password = "s3cr3t"

        self.commcare_user = CommCareUser.create(self.domain, self.username, self.password)
        self.commcare_user.save()

        self.other_user = CommCareUser.create(self.domain, self.other_username, self.password)
        self.other_user.save()

    def tearDown(self):
        for user in CommCareUser.all():
            user.delete()
        delete_all_cases()
        delete_all_xforms()

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
            relationships=[
                 CaseRelationship(CaseStructure(case_id=parent_id))
            ]
        ))
        # confirm the child has an index, and 1 form
        self.assertEqual(1, len(child.indices))
        self.assertEqual(parent_id, child.indices[0].referenced_id)
        self.assertEqual(1, len(child.xform_ids))

        # simulate parent deletion
        parent.doc_type = 'CommCareCase-Deleted'
        parent.save()

        # call the remove index task
        remove_indices_from_deleted_cases(self.domain, [parent_id])

        # check that the index is removed via a new form
        child = CommCareCase.get(child_id)
        self.assertEqual(0, len(child.indices))
        self.assertEqual(2, len(child.xform_ids))


    @mock.patch("casexml.apps.case.cleanup.rebuild_case")
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
        casexml = ElementTree.tostring(caseblock.as_xml())
        submit_case_blocks(casexml, self.domain, user_id=self.other_user._id)

        self.other_user.retire()

        rebuild_case.assert_called_once_with(case_id)

    @mock.patch("casexml.apps.case.cleanup.rebuild_case")
    def test_dont_rebuild(self, rebuild_case):
        """ Don't rebuild cases that are owned by other users """

        case_id = uuid.uuid4().hex
        caseblock = CaseBlock(
            create=True,
            case_id=case_id,
            owner_id=self.commcare_user._id,
            user_id=self.commcare_user._id,
        )
        casexml = ElementTree.tostring(caseblock.as_xml())
        submit_case_blocks(casexml, self.domain, user_id=self.commcare_user._id)

        self.other_user.retire()

        self.assertEqual(rebuild_case.call_count, 0)

    @mock.patch("casexml.apps.case.cleanup.rebuild_case")
    def test_multiple_case_blocks_all_rebuilt(self, rebuild_case):
        """ Rebuild all cases in forms with multiple case blocks """

        case_ids = [uuid.uuid4().hex, uuid.uuid4().hex, uuid.uuid4().hex]

        caseblocks = [CaseBlock(
            create=True,
            case_id=case_id,
            owner_id=self.commcare_user._id,
            user_id=self.commcare_user._id,
        ) for case_id in case_ids]
        casexmls = [ElementTree.tostring(caseblock.as_xml()) for caseblock in caseblocks]
        submit_case_blocks(casexmls, self.domain, user_id=self.other_user._id)

        self.other_user.retire()

        expected_call_args = [mock.call(case_id) for case_id in case_ids]

        self.assertEqual(rebuild_case.call_count, len(case_ids))
        self.assertItemsEqual(rebuild_case.call_args_list, expected_call_args)

    @mock.patch("casexml.apps.case.cleanup.rebuild_case")
    def test_multiple_case_blocks_some_deleted(self, rebuild_case):
        """ Don't rebuild deleted cases """

        case_ids = [uuid.uuid4().hex, uuid.uuid4().hex, uuid.uuid4().hex]

        caseblocks = [CaseBlock(
            create=True,
            case_id=case_id,
            owner_id=self.commcare_user._id,
            user_id=self.commcare_user._id,
        ) for case_id in case_ids]
        casexmls = [ElementTree.tostring(caseblock.as_xml()) for caseblock in caseblocks]
        submit_case_blocks(casexmls, self.domain, user_id=self.other_user._id)

        # This case will get deleted when the user is retired
        case = CommCareCase.get(case_ids[0])
        case.owner_id = self.other_user._id
        case.save()

        self.other_user.retire()

        expected_call_args = [mock.call(case_id) for case_id in case_ids[1:]]

        self.assertEqual(rebuild_case.call_count, len(case_ids) - 1)
        self.assertItemsEqual(rebuild_case.call_args_list, expected_call_args)
