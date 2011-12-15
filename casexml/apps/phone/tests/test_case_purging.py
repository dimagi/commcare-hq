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

class CasePurgeTest(TestCase):
    """
    Tests the logic for purging cases.
    """
        
    def setUp(self):
        # clear cases
        for item in XFormInstance.view("couchforms/by_xmlns", include_docs=True, reduce=False).all():
            item.delete()
        for case in CommCareCase.view("case/by_xform_id", include_docs=True).all():
            case.delete()
        for log in SyncLog.view("phone/sync_logs_by_user", include_docs=True, reduce=False).all():
            log.delete()
    
    def testBasicPurge(self):
        """
        Tests that purging cases works as advertised
        """
        # create a case and attach it to someone.
        user = dummy_user()
        case_id = uid.new()
        case_block = CaseBlock(
            create=True,
            case_id=case_id,
            case_name="purgeme",
            case_type="sometype",
            user_id=user.user_id, # must match
            external_id=uid.new(), # must match
            update={'foo': "bar"},
        ).as_xml(format_datetime=date_to_xml_string)
        
        post_case_blocks([case_block])
        
        # have to sleep for annyoing timestamp reasons
        time.sleep(1)
        check_user_has_case(self, user, case_block, line_by_line=True)
        
        [sync_log] = SyncLog.view("phone/sync_logs_by_user", include_docs=True, reduce=False).all()
        check_user_has_case(self, user, case_block, should_have=False, restore_id=sync_log.get_id)
        
        # close it from someone else.
        close_block = CaseBlock(
            case_id=case_id,
            update={"user_id": uid.new()},
            close=True
        ).as_xml(format_datetime=date_to_xml_string)
        
        post_case_blocks([close_block])
        
        # make sure the case comes back to be purged
        expected = CaseBlock(case_id=case_id, close=True).as_xml(format_datetime=date_to_xml_string)
        # TODO: this is currently broken until we have a way to tie 
        # it to a different user
#        check_user_has_case(self, user, expected, should_have=True, line_by_line=True,
#                            restore_id=sync_log.get_id)
#        
