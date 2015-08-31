import uuid
from django.test import TestCase
from mock import patch
from casexml.apps.case.const import CASE_ACTION_UPDATE
from casexml.apps.case.models import CommCareCase, CommCareCaseAction
from casexml.apps.case.sharedmodels import CommCareCaseIndex
from casexml.apps.phone.models import SyncLog, CaseState, SimplifiedSyncLog
from couchforms.models import XFormInstance


class SyncLogAssertionTest(TestCase):

    def test_update_dependent_case(self):
        sync_log = SyncLog(
            cases_on_phone=[
                CaseState(
                    case_id='bran',
                    indices=[CommCareCaseIndex(identifier='legs', referenced_id='hodor')],
                ),
            ],
            dependent_cases_on_phone=[CaseState(case_id='hodor')]
        )
        xform_id = uuid.uuid4().hex
        xform = XFormInstance(_id=xform_id)
        form_actions = [CommCareCaseAction(action_type=CASE_ACTION_UPDATE,)]
        with patch.object(CommCareCase, 'get_actions_for_form', return_value=form_actions):
            parent_case = CommCareCase(_id='hodor')
            # before this test was added, the following call raised a SyncLogAssertionError on legacy logs.
            # this test just ensures it doesn't still do that.
            for log in [sync_log, SimplifiedSyncLog.from_other_format(sync_log)]:
                log.update_phone_lists(xform, [parent_case])

    def test_update_dependent_case_owner_still_present(self):
        dependent_case_state = CaseState(case_id="d1", indices=[])
        sync_log = SyncLog(
            cases_on_phone=[
                CaseState(case_id="c1", indices=[
                    CommCareCaseIndex(identifier="d1-id", referenced_id="d1")
                ])
            ],
            dependent_cases_on_phone=[dependent_case_state],
            owner_ids_on_phone=['user1']
        )
        xform_id = uuid.uuid4().hex
        xform = XFormInstance(_id=xform_id)
        form_actions = [CommCareCaseAction(action_type=CASE_ACTION_UPDATE, updated_known_properties={'owner_id': 'user2'})]
        with patch.object(CommCareCase, 'get_actions_for_form', return_value=form_actions):
            parent_case = CommCareCase(_id='d1')
            # before this test was added, the following call raised a ValueError on legacy logs.
            for log in [sync_log, SimplifiedSyncLog.from_other_format(sync_log)]:
                log.update_phone_lists(xform, [parent_case])
                self.assertIn(dependent_case_state, log.test_only_get_dependent_cases_on_phone())
