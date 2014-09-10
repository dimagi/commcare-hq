from django.test import TestCase
from casexml.apps.case.mock import CaseBlock
from casexml.apps.case.models import CommCareCase
from casexml.apps.case.util import post_case_blocks
from casexml.apps.case.xml import V2
from corehq.apps.sofabed.models import CaseData
from datetime import date, datetime, timedelta
from casexml.apps.case.tests import delete_all_xforms, delete_all_cases

TEST_DOMAIN = 'test'

class CaseDataTests(TestCase):
    
    def setUp(self):
        delete_all_xforms()
        delete_all_cases()

        self.case_id = 'test_case_1'
        self.date_modified = datetime.now() - timedelta(hours=1)
        self.date_modified = self.date_modified.replace(microsecond=0)
        post_case_blocks([
            CaseBlock(create=True, case_id=self.case_id, owner_id="owner", user_id='user',
                      case_type='c_type', case_name='c_name', external_id='external_id',
                      date_modified=self.date_modified, version=V2, update={'foo': 'bar'}
            ).as_xml(format_datetime=None)
        ], {'domain': TEST_DOMAIN})

        instance = CommCareCase.get(self.case_id)
        self.casedata = CaseData.create_or_update_from_instance(instance)

    def test_create(self):
        self.assertEqual(self.date_modified, self.casedata.opened_on)
        self.assertEqual(self.date_modified, self.casedata.modified_on)
        self.assertEqual(False, self.casedata.closed)
        self.assertEqual('c_type', self.casedata.type)
        self.assertEqual('c_name', self.casedata.name)
        self.assertEqual('external_id', self.casedata.external_id)
        self.assertEqual(V2, self.casedata.version)
        self.assertEqual('owner', self.casedata.owner_id)
        self.assertEqual('user', self.casedata.modified_by)

        actions = self.casedata.actions.all()
        self.assertEqual(2, len(actions))
        for action in actions:
            if action.index == 0:
                self.assertEqual('create', action.action_type)
            if action.index == 1:
                self.assertEqual('update', action.action_type)
            self.assertEqual(date.today(), action.date.date())
            self.assertEqual(date.today(), action.server_date.date())
            self.assertEqual('user', action.user_id)

    def test_update(self):
        date_modified = datetime.now().replace(microsecond=0)
        post_case_blocks([
            CaseBlock(close=True, case_id=self.case_id, user_id='user2', date_modified=date_modified,
                      version=V2).as_xml(format_datetime=None)
        ], {'domain': TEST_DOMAIN})

        instance = CommCareCase.get(self.case_id)
        updateddata = CaseData.create_or_update_from_instance(instance)
        self.assertEqual(date_modified, updateddata.modified_on)
        self.assertEqual('user2', updateddata.modified_by)
        self.assertEqual(date_modified, updateddata.closed_on)
        self.assertEqual(True, updateddata.closed)

        actions = updateddata.actions.all()
        self.assertEqual(3, len(actions))
        for action in actions:
            if action.index == 2:
                self.assertEqual('close', action.action_type)
                self.assertEqual(date.today(), action.date.date())
                self.assertEqual(date.today(), action.server_date.date())
                self.assertEqual('user2', action.user_id)
