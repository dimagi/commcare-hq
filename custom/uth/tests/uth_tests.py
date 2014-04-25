import uuid
from django.test import TestCase
from casexml.apps.case.mock import CaseBlock
from casexml.apps.case.xml import V2
from corehq.apps.users.models import CommCareUser
from corehq.apps.users.util import format_username
from corehq.apps.domain.shortcuts import create_domain
from dimagi.utils.parsing import json_format_datetime
from casexml.apps.case.util import post_case_blocks

from custom.uth.utils import match_case


class UTHTests(TestCase):

    def create_scan_case(self, user_id, serial, scan_id, scan_uploaded=False):
        case_id = uuid.uuid4().hex
        case_block = CaseBlock(
            create=True,
            case_id=case_id,
            case_name='scan',
            case_type='magic_vscan_type',
            user_id=user_id,
            owner_id=user_id,
            version=V2,
            update={
                'scan_id': scan_id,
                'vscan_serial': serial,
                'scan_uploaded': scan_uploaded
            }
        ).as_xml(format_datetime=json_format_datetime)
        post_case_blocks([case_block], {'domain': 'vscan_domain'})

        return case_id

    def setUp(self):
        self.domain = create_domain('vscan_domain')

        username = format_username('vscan_user', 'vscan_domain')

        self.vscan_user = CommCareUser.get_by_username(username) or CommCareUser.create(
            'vscan_domain',
            username,
            'secret'
        )

        self.case_id = self.create_scan_case(
            self.vscan_user._id,
            'VH014466XK',
            '123123'
        )

    def testFindsCorrectCase(self):
        case = match_case('vscan_domain', 'VH014466XK', '123123', '')
        self.assertEqual(self.case_id, case._id)

    def testWrongScanID(self):
        case = match_case('vscan_domain', 'VH014466XK', 'wrong', '')
        self.assertIsNone(case)

    def testWrongSerial(self):
        case = match_case('vscan_domain', 'wrong', '123123', '')
        self.assertIsNone(case)

    def testGetsNewestWithTwoCases(self):
        case_2_id = self.create_scan_case(
            self.vscan_user._id,
            'VH014466XK',
            '123123'
        )

        case = match_case('vscan_domain', 'VH014466XK', '123123', '')
        self.assertEqual(case_2_id, case._id)

    def testGetsNewestBasedOnScanProperty(self):
        pass

    def testGetsOnlyUnmarkedCases(self):
        self.create_scan_case(
            self.vscan_user._id,
            'VH014466XK',
            '123123',
            scan_uploaded=True
        )

        case = match_case('vscan_domain', 'VH014466XK', '123123', '')
        self.assertEqual(self.case_id, case._id)
