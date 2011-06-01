from casexml.apps.case.util import *
from casexml.apps.case.models.couch import *
from datetime import datetime

def test_close_case_xml():
    case_xml = get_close_case_xml(time=datetime.utcnow(), case_id="blah")
    print case_xml

def test_close_referral_xml():
    referral_xml = get_close_referral_xml(time=datetime.utcnow(), case_id="blah", referral_id="blah", referral_type="blah")
    print referral_xml

def test_close(case_id, referral_indexes=[]):
    case = CommCareCase.get(case_id)
    for i in referral_indexes:
        case.force_close_referral(case.referrals[i])
    case.force_close()