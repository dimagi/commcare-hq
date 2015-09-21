import uuid
from django.test import TestCase
from casexml.apps.case.mock import CaseBlock
from casexml.apps.case.xml import V2
from corehq.apps.users.models import CommCareUser
from corehq.apps.users.util import format_username
from corehq.apps.domain.shortcuts import create_domain
from casexml.apps.case.util import post_case_blocks
import os
from custom.uth import utils
from casexml.apps.case.tests import delete_all_xforms, delete_all_cases
from casexml.apps.case.models import CommCareCase
from custom.uth.const import UTH_DOMAIN, UTH_CASE_TYPE
from couchdbkit import MultipleResultsFound


class UTHTests(TestCase):
    def create_scan_case(self, user_id, serial, scan_id, scan_time, scan_status=''):
        case_id = uuid.uuid4().hex
        case_block = CaseBlock(
            create=True,
            case_id=case_id,
            case_name='scan',
            case_type=UTH_CASE_TYPE,
            user_id=user_id,
            owner_id=user_id,
            version=V2,
            update={
                'exam_number': scan_id,
                'scanner_serial': serial,
                'scan_status': scan_status,
                'scan_time': scan_time
            }
        ).as_xml()
        post_case_blocks([case_block], {'domain': UTH_DOMAIN})

        return case_id

    def setUp(self):
        delete_all_xforms()
        delete_all_cases()

        self.domain = create_domain(UTH_DOMAIN)

        username = format_username('vscan_user', UTH_DOMAIN)

        self.vscan_user = CommCareUser.get_by_username(username) or CommCareUser.create(
            UTH_DOMAIN,
            username,
            'secret'
        )

        self.case_id = self.create_scan_case(
            self.vscan_user._id,
            'VH014466XK',
            '123123',
            '2014-03-28T10:48:49Z'
        )


class ScanLookupTests(UTHTests):
    def testFindsCorrectCase(self):
        case = utils.match_case('VH014466XK', '123123', '')
        self.assertEqual(self.case_id, case._id)

    def testWrongScanID(self):
        case = utils.match_case('VH014466XK', 'wrong', '')
        self.assertIsNone(case)

    def testWrongSerial(self):
        case = utils.match_case('wrong', '123123', '')
        self.assertIsNone(case)

    def testErrorsWithTwoCases(self):
        self.create_scan_case(
            self.vscan_user._id,
            'VH014466XK',
            '123123',
            '2014-03-29T10:48:49Z'
        )
        self.create_scan_case(
            self.vscan_user._id,
            'VH014466XK',
            '123123',
            '2014-03-22T10:48:49Z'
        )

        self.assertRaises(
            MultipleResultsFound,
            lambda: utils.match_case('VH014466XK', '123123', '')
        )

    def testGetsOnlyUnmarkedCases(self):
        self.create_scan_case(
            self.vscan_user._id,
            'VH014466XK',
            '123123',
            '2014-03-30T10:48:49Z',
            scan_status='scan_complete'
        )

        case = utils.match_case('VH014466XK', '123123', '')
        self.assertEqual(self.case_id, case._id)


class VscanTests(UTHTests):
    def pack_directory(self, directory):
        # name of the test directory we're packing
        packed_directory = {}

        for root, dirs, files in os.walk(directory):
            for f in files:
                packed_directory[
                    os.path.join(os.path.split(directory)[-1], f)
                ] = open(os.path.join(root, f))

        return packed_directory

    def testAttachments(self):
        self.assertEqual(len(CommCareCase.get(self.case_id).case_attachments), 0)
        scan_path = os.path.join(
            os.path.dirname(__file__),
            'data',
            'vscan',
            'VH014466XK_000016_20130722T175057'
        )
        files = self.pack_directory(scan_path)
        utils.attach_images_to_case(self.case_id, files)

        self.assertEqual(len(CommCareCase.get(self.case_id).case_attachments), 3)


class ImageUploadTests(UTHTests):

    def pack_directory(self, directory):
        # name of the test directory we're packing
        packed_directory = {}

        for root, dirs, files in os.walk(directory):
            for f in files:
                packed_directory[f] = open(os.path.join(root, f))

        return packed_directory

    def setUp(self):
        super(ImageUploadTests, self).setUp()

        path = os.path.join(
            os.path.dirname(__file__),
            'data',
            'sonosite',
            'complete'
        )

        self.files = self.pack_directory(path)

    def testRelatedMethods(self):
        patient_config = self.files['PT_PPS.XML'].read()
        self.assertEqual(
            'JHUYIIYIUIY',
            utils.get_case_id(patient_config)
        )
        self.assertEqual(
            '1.2.840.114340.03.000008251017183037.2.20130821.094421.0000080',
            utils.get_study_id(patient_config)
        )

    def testUpload(self):
        result = utils.create_case(self.case_id, self.files, self.case_id)

        self.assertEqual(len(result), 1)

        case = result[0]

        self.assertEqual(case.type, 'sonosite_upload')
        self.assertEqual(len(case.case_attachments), 3)
        self.assertEqual(case.patient_case_id, self.case_id)
        self.assertEqual(self.case_id, case.indices[0].referenced_id)
        self.assertEqual('child', case.indices[0].referenced_type)
        self.assertEqual('patient_id', case.indices[0].identifier)
