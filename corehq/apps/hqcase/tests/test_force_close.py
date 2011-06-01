from casexml.apps.case.util import get_close_case_xml, get_close_referral_xml
from casexml.apps.case.models import CommCareCase
from datetime import datetime
from django.test import TestCase


class ForceCloseCaseTest(TestCase):

    def test_close_case_xml(self):
        case_xml = get_close_case_xml(time=datetime.utcnow(), case_id="blah")
        print case_xml
    
    def test_close_referral_xml(self):
        referral_xml = get_close_referral_xml(time=datetime.utcnow(), case_id="blah", referral_id="blah", referral_type="blah")
        print referral_xml
    
    def test_close(self):
        return 
        #there's no way this will work
        case_id = "foo"
        referral_indexes=[]
        case = CommCareCase.get(case_id)
        for i in referral_indexes:
            case.force_close_referral(case.referrals[i])
        case.force_close()