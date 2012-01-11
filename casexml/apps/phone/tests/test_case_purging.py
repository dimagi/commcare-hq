from django.test import TestCase
import os
import time
from couchforms.util import post_xform_to_couch
from casexml.apps.case.models import CommCareCase
from casexml.apps.case.tests.util import check_xml_line_by_line, CaseBlock,\
    check_user_has_case
from casexml.apps.case.signals import process_cases
from casexml.apps.phone.models import SyncLog
from casexml.apps.phone.restore import generate_restore_payload
from casexml.apps.phone.tests import const
from casexml.apps.phone.tests.dummy import dummy_user
from couchforms.models import XFormInstance
from dimagi.utils.couch import uid
from casexml.apps.phone.xml import date_to_xml_string
from casexml.apps.case.util import post_case_blocks
from casexml.apps.case.xml import V2

class CasePurgeTest(TestCase):
    """
    Tests the logic for purging cases.
    """
        
    def setUp(self):
        # clear cases
        for item in XFormInstance.view("couchforms/by_xmlns", include_docs=True, 
                                       reduce=False).all():
            item.delete()
        for case in CommCareCase.view("case/by_user", reduce=False, include_docs=True).all():
            case.delete()
        for log in SyncLog.view("phone/sync_logs_by_user", include_docs=True, 
                                reduce=False).all():
            log.delete()
    
    def testBasicPurge(self):
        """
        Tests that purging cases works as advertised
        """
        # create a case and attach it to someone.
        raise Exception("This test is no longer valid and needs to be fixed if anyone cares")
        
        user = dummy_user()
        case_id = uid.new()
        case_block = CaseBlock(
            create=True,
            case_id=case_id,
            case_name="purgeme",
            case_type="sometype",
            user_id=user.user_id,  # must match
            update={'foo': "bar"},
            version=V2             # these only work on v2 cases
        ).as_xml(format_datetime=date_to_xml_string)
        
        post_case_blocks([case_block])
        
        # have to sleep for annoying timestamp reasons
        time.sleep(1)
        check_user_has_case(self, user, case_block, line_by_line=True, 
                            version=V2)
        
        [sync_log] = SyncLog.view("phone/sync_logs_by_user", include_docs=True,
                                   reduce=False).all()
        check_user_has_case(self, user, case_block, should_have=False, 
                            restore_id=sync_log.get_id, version=V2)
        
        # close it from someone else.
        second_user = uid.new()
        close_block = CaseBlock(
            case_id=case_id,
            user_id=second_user,
            close=True,
            version=V2
        ).as_xml(format_datetime=date_to_xml_string)
        
        post_case_blocks([close_block])
        
        # make sure the case comes back to be purged
        expected = CaseBlock(case_id=case_id, close=True, version=V2, 
                             user_id=second_user).as_xml\
                    (format_datetime=date_to_xml_string)
        check_user_has_case(self, user, expected, should_have=True, 
                            line_by_line=True, restore_id=sync_log.get_id, 
                            version=V2)

