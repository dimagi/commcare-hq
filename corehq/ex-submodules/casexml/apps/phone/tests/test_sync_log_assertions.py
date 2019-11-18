import uuid

from django.test import TestCase

from mock import patch

from casexml.apps.case.const import CASE_ACTION_UPDATE
from casexml.apps.case.models import CommCareCase, CommCareCaseAction
from casexml.apps.phone.models import CaseState, IndexTree, SimplifiedSyncLog
from couchforms.models import XFormInstance

from corehq.form_processor.tests.utils import use_sql_backend


class SyncLogAssertionTest(TestCase):

    def test_update_dependent_case(self):
        sync_log = SimplifiedSyncLog(
            case_ids_on_phone={'bran', 'hodor'},
            dependent_case_ids_on_phone={'hodor'},
            index_tree=IndexTree(indices={
                'bran': {'legs': 'hodor'}
            }),
            user_id="someuser"
        )
        xform_id = uuid.uuid4().hex
        xform = XFormInstance(_id=xform_id)
        form_actions = [CommCareCaseAction(action_type=CASE_ACTION_UPDATE,)]
        with patch.object(CommCareCase, 'get_actions_for_form', return_value=form_actions):
            parent_case = CommCareCase(_id='hodor')
            # before this test was added, the following call raised a SyncLogAssertionError on legacy logs.
            # this test just ensures it doesn't still do that.
            sync_log.update_phone_lists(xform, [parent_case])

    def test_update_dependent_case_owner_still_present(self):
        sync_log = SimplifiedSyncLog(
            domain="domain",
            case_ids_on_phone={'c1', 'd1'},
            dependent_case_ids_on_phone={'d1'},
            index_tree=IndexTree(indices={
                'c1': {'d1-id': 'd1'}
            }),
            user_id="user",
            owner_ids_on_phone={'user1'}
        )

        dependent_case_state = CaseState(case_id="d1", indices=[])
        xform_id = uuid.uuid4().hex
        xform = XFormInstance(_id=xform_id)
        form_actions = [CommCareCaseAction(action_type=CASE_ACTION_UPDATE, updated_known_properties={'owner_id': 'user2'})]
        with patch.object(CommCareCase, 'get_actions_for_form', return_value=form_actions):
            parent_case = CommCareCase(_id='d1')
            # before this test was added, the following call raised a ValueError on legacy logs.
            sync_log.update_phone_lists(xform, [parent_case])
            self.assertIn(dependent_case_state, sync_log.test_only_get_dependent_cases_on_phone())


@use_sql_backend
class SyncLogAssertionTestSQL(SyncLogAssertionTest):
    pass
