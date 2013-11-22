from casexml.apps.case.tests.util import check_xml_line_by_line, bootstrap_case_from_xml
from casexml.apps.case.util import get_close_case_xml, get_close_referral_xml
from casexml.apps.case.models import CommCareCase
from datetime import datetime
from django.test import TestCase
from corehq.apps.domain.shortcuts import create_domain
from dimagi.utils.parsing import json_format_datetime

CLOSE_CASE_XML = """<?xml version='1.0' ?>
<system version="1" uiVersion="1" xmlns:jrm="http://openrosa.org/jr/xforms" xmlns="http://commcarehq.org/case">
    <meta>
        <deviceID />
        <timeStart>{time}</timeStart>
        <timeEnd>{time}</timeEnd>
        <username>system</username>
        <userID />
        <uid>uid_blah_1</uid>
    </meta>
    <case>
        <case_id>uid_blah</case_id>
        <user_id />
        <date_modified>{time}</date_modified>
        <close />
    </case>
</system>"""

CLOSE_REFERRAL_XML = """<?xml version='1.0' ?>
<system version="1" uiVersion="1" xmlns:jrm="http://openrosa.org/jr/xforms" xmlns="http://commcarehq.org/case">
    <meta>
        <deviceID />
        <timeStart>{time}</timeStart>
        <timeEnd>{time}</timeEnd>
        <username>system</username>
        <userID />
        <uid>uid_blah_2</uid>
    </meta>
    <case>
        <case_id>blah</case_id>
        <user_id />
        <date_modified>{time}</date_modified>
        <referral>
            <referral_id>blah</referral_id>
            <update>
                <referral_type>blah</referral_type>
                <date_closed>{time}</date_closed>
            </update>
        </referral>
    </case>
</system>"""

class ForceCloseCaseTest(TestCase):

    def test_close_case_xml(self):
        time = datetime.utcnow()
        case_xml = get_close_case_xml(time=time, case_id="uid_blah", uid="uid_blah_1")
        check_xml_line_by_line(self, case_xml, CLOSE_CASE_XML.format(time=json_format_datetime(time)))
    
    def test_close_referral_xml(self):
        time = datetime.utcnow()
        referral_xml = get_close_referral_xml(
            time=time,
            case_id="blah",
            referral_id="blah",
            referral_type="blah",
            uid="uid_blah_2"
        )
        check_xml_line_by_line(self, referral_xml, CLOSE_REFERRAL_XML.format(time=json_format_datetime(time)))
    
    def test_close(self):
        case_id = 'uid_blah_3'
        domain = "test.domain"
        create_domain(domain)
        case = bootstrap_case_from_xml(
            self,
            filename='create.xml',
            case_id_override=case_id,
            domain=domain,
        )
        case.save()
        referral_indexes=[]
        case = CommCareCase.get(case_id)
        for i in referral_indexes:
            case.force_close_referral(case.referrals[i])
        case.force_close("/a/{domain}/receiver".format(domain=domain))
        case = CommCareCase.get(case_id)
        self.assertTrue(case.closed)