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

    def setUp(self):
        self.domain = create_domain('vscan_domain')
        self.vscan_user = CommCareUser.create(
            'vscan_domain',
            format_username('vscan_user', 'vscan_domain'),
            'secret'
        )

        self.case_id = uuid.uuid4().hex
        case_block = CaseBlock(
            create=True,
            case_id=self.case_id,
            case_name='scan',
            case_type='magic_vscan_type',
            user_id=self.vscan_user._id,
            owner_id=self.vscan_user._id,
            version=V2,
            update={
                'scan_id': '123123',
                'vscan_serial': 'VH014466XK',
            }
        ).as_xml(format_datetime=json_format_datetime)
        post_case_blocks([case_block], {'domain': 'vscan_domain'})

    def testFindsCorrectCase(self):
        case = match_case('vscan_domain', 'VH014466XK', '123123', '')
        self.assertEqual(self.case_id, case._id)
