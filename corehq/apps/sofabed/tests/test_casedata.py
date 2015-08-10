from django.test import TestCase
from casexml.apps.case.mock import CaseBlock
from casexml.apps.case.models import CommCareCase
from casexml.apps.case.util import post_case_blocks
from casexml.apps.case.xml import V2
from corehq.apps.sofabed.models import CaseData, CASE_NAME_LEN
from datetime import date, datetime, timedelta
from casexml.apps.case.tests import delete_all_xforms, delete_all_cases

TEST_DOMAIN = 'test'
TEST_NAME_LEN = CASE_NAME_LEN-8


class CaseDataTests(TestCase):

    def setUp(self):
        delete_all_xforms()
        delete_all_cases()

        post_case_blocks([
            CaseBlock(
                create=True,
                case_id='mother_case_id',
                case_type='mother-case',
                version=V2,
            ).as_xml()
        ], {'domain': TEST_DOMAIN})

        self.case_id = 'test_case_1'
        self.date_modified = datetime.utcnow() - timedelta(hours=1)
        self.date_modified = self.date_modified.replace(microsecond=0)
        post_case_blocks([
            CaseBlock(
                create=True,
                case_id=self.case_id,
                owner_id="owner",
                user_id='user',
                case_type='c_type',
                case_name=('a' * TEST_NAME_LEN) + '123456789',
                external_id='external_id',
                date_modified=self.date_modified,
                version=V2,
                update={'foo': 'bar'},
                index={'mom': ('mother-case', 'mother_case_id')}
            ).as_xml()
        ], {'domain': TEST_DOMAIN})

        instance = CommCareCase.get(self.case_id)
        self.casedata = CaseData.create_or_update_from_instance(instance)

    def test_create(self):
        self.assertEqual(self.date_modified, self.casedata.opened_on)
        self.assertEqual(self.date_modified, self.casedata.modified_on)
        self.assertEqual(False, self.casedata.closed)
        self.assertEqual('c_type', self.casedata.type)
        self.assertEqual(('a' * TEST_NAME_LEN) + '12345...', self.casedata.name)
        self.assertEqual('external_id', self.casedata.external_id)
        self.assertEqual(V2, self.casedata.version)
        self.assertEqual('owner', self.casedata.owner_id)
        self.assertEqual('user', self.casedata.modified_by)

        actions = self.casedata.actions.all()
        self.assertEqual(3, len(actions))
        for action in actions:
            self.assertEqual(self.date_modified.date(), action.date.date())
            self.assertEqual(date.today(), action.server_date.date())
            self.assertEqual('user', action.user_id)
            self.assertEqual('owner', action.case_owner)
            self.assertEqual('c_type', action.case_type)

            if action.index == 0:
                self.assertEqual('create', action.action_type)
            if action.index == 1:
                self.assertEqual('update', action.action_type)
            if action.index == 2:
                self.assertEqual('index', action.action_type)

        indices = self.casedata.indices.all()
        self.assertEqual(1, len(indices))
        self.assertEqual('mom', indices[0].identifier)
        self.assertEqual('mother-case', indices[0].referenced_type)
        self.assertEqual('mother_case_id', indices[0].referenced_id)

    def test_update(self):
        post_case_blocks([
            CaseBlock(
                create=True,
                case_id='grand_mother_case_id',
                case_type='mother-case',
                owner_id='owner',
                version=V2,
            ).as_xml()
        ], {'domain': TEST_DOMAIN})

        date_modified = datetime.utcnow()
        post_case_blocks([
            CaseBlock(
                close=True,
                case_id=self.case_id,
                user_id='user2',
                date_modified=date_modified,
                version=V2,
                index={'gmom': ('mother-case', 'grand_mother_case_id')}
            ).as_xml()
        ], {'domain': TEST_DOMAIN})

        instance = CommCareCase.get(self.case_id)
        updateddata = CaseData.create_or_update_from_instance(instance)
        self.assertEqual(date_modified, updateddata.modified_on)
        self.assertEqual('user2', updateddata.modified_by)
        self.assertEqual(date_modified, updateddata.closed_on)
        self.assertEqual(True, updateddata.closed)

        actions = updateddata.actions.all()
        self.assertEqual(5, len(actions))
        for action in actions:
            if action.index == 4:
                self.assertEqual('close', action.action_type)
                self.assertEqual(date.today(), action.date.date())
                self.assertEqual(date.today(), action.server_date.date())
                self.assertEqual('user2', action.user_id)
                self.assertEqual('owner', action.case_owner)
                self.assertEqual('c_type', action.case_type)

        indices = self.casedata.indices.all()
        self.assertEqual(2, len(indices))
        self.assertEqual('gmom', indices[0].identifier)
        self.assertEqual('mother-case', indices[0].referenced_type)
        self.assertEqual('grand_mother_case_id', indices[0].referenced_id)
        self.assertEqual('mom', indices[1].identifier)
        self.assertEqual('mother-case', indices[1].referenced_type)
        self.assertEqual('mother_case_id', indices[1].referenced_id)

    def test_empty_name(self):
        case_id = 'case_with_no_name'
        post_case_blocks([
            CaseBlock(
                create=True,
                case_id=case_id,
                case_type='nameless',
                version=V2,
            ).as_xml()
        ], {'domain': TEST_DOMAIN})

        instance = CommCareCase.get(case_id)
        casedata = CaseData.create_or_update_from_instance(instance)
        self.assertIsNotNone(casedata)
        self.assertEqual('', casedata.name)

    def test_empty_owner_id(self):
        case_id = 'case_with_no_owner'
        post_case_blocks([
            CaseBlock(
                create=True,
                case_id=case_id,
                user_id='user',
                case_type='c_type',
                case_name='bob',
                date_modified=self.date_modified,
                version=V2,
                update={'foo': 'bar'},
            ).as_xml()
        ], {'domain': TEST_DOMAIN})

        instance = CommCareCase.get(case_id)
        casedata = CaseData.create_or_update_from_instance(instance)
        self.assertIsNotNone(casedata)
        self.assertEqual('user', casedata.case_owner)


