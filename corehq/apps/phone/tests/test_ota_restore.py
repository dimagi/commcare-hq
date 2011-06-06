from django.test import TestCase
import os
from couchforms.util import post_xform_to_couch
from casexml.apps.case.models import CommCareCase
from django.test.client import Client
from django.core.urlresolvers import reverse
from casexml.apps.case.tests.util import check_xml_line_by_line
from casexml.apps.case.signals import process_cases

class OtaRestoreTest(TestCase):
    """Tests OTA Restore"""
    
    def setUp(self):
        # clear cases
        for case in CommCareCase.view("case/by_xform_id", include_docs=True).all():
            case.delete()
        
    def testWithReferrals(self):
        self.assertEqual(0, len(CommCareCase.view("case/by_xform_id", include_docs=True).all()))
        file_path = os.path.join(os.path.dirname(__file__), "data", "case_create.xml")
        with open(file_path, "rb") as f:
            xml_data = f.read()
        form = post_xform_to_couch(xml_data)
        process_cases(sender="testharness", xform=form)
        [newcase] = CommCareCase.view("case/by_xform_id", include_docs=True).all()
        self.assertEqual(0, len(newcase.referrals))
        file_path = os.path.join(os.path.dirname(__file__), "data", "case_refer.xml")
        with open(file_path, "rb") as f:
            xml_data = f.read()
        form = post_xform_to_couch(xml_data)
        process_cases(sender="testharness", xform=form)
        [updated_case] = CommCareCase.view("case/by_xform_id", include_docs=True).all()
        self.assertEqual(1, len(updated_case.referrals))
        c = Client()
        response = c.get(reverse("single_case_xml", args=["fakedomain", updated_case.get_id]))
        expected_response = """<case>
    <case_id>IKA9G79J4HDSPJLG3ER2OHQUY</case_id> 
    <date_modified>2011-02-19</date_modified>
    <create>
        <case_type_id>cc_mobilize_client</case_type_id> 
        <user_id>ae179a62-38af-11e0-b6a3-005056aa7fb5</user_id> 
        <case_name>SIEGEL-ROBERT-5412366523984</case_name> 
        <external_id>5412366523984</external_id>
    </create>
    <update>
       <Problems></Problems>
       <abdominalpain></abdominalpain>
       <address></address>
       <addstaff1></addstaff1>
       <addstaff2></addstaff2>
       <allmeds_likert></allmeds_likert>
       <arv_lasttreatment></arv_lasttreatment>
       <arv_missedtreatments></arv_missedtreatments>
       <arv_taking></arv_taking>
       <assistance></assistance>
       <confusion></confusion>
       <contact_age_alt></contact_age_alt>
       <contact_name_alt></contact_name_alt>
       <contact_phone_alt></contact_phone_alt>
       <deafness></deafness>
       <depression></depression>
       <diarrhea></diarrhea>
       <dob>2011-02-11</dob>
       <gender>male</gender>
       <given_name>ROBERT</given_name>
       <imbalance></imbalance>
       <injectionother></injectionother>
       <injectiontype></injectiontype>
       <jaundice></jaundice>
       <jointpain></jointpain>
       <legal_name>ROBERT SIEGEL</legal_name>
       <musclepain></musclepain>
       <muscleweakness></muscleweakness>
       <nickname>BOB</nickname>
       <other></other>
       <patient_dot>123</patient_dot>
       <patient_id>5412366523984</patient_id>
       <phone_number>1</phone_number>
       <place></place>
       <psychosis></psychosis>
       <rash></rash>
       <request_name>ME</request_name>
       <request_rank>staff_nurse</request_rank>
       <request_reason></request_reason>
       <request_timestamp>2011-02-19 16:46:28</request_timestamp>
       <ringing></ringing>
       <seizures></seizures>
       <short_name>SIEGEL, ROBERT</short_name>
       <sleeping></sleeping>
       <staffnumber1></staffnumber1>
       <staffnumber2></staffnumber2>
       <staffnumber3></staffnumber3>
       <surname>SIEGEL</surname>
       <swelling></swelling>
       <tb_lasttreatment></tb_lasttreatment>
       <tb_missedtreatments></tb_missedtreatments>
       <tbtype></tbtype>
       <tingling></tingling>
       <tribal_area></tribal_area>
       <txoutcome></txoutcome>
       <txstart>2011-02-11</txstart>
       <vision></vision>
       <vomiting></vomiting>
    </update>
    <referral> 
        <referral_id>V2RLNE4VQYEMZRGYSOMLYU4PM</referral_id>
        <followup_date>2011-02-20</followup_date>
        <open>
            <referral_types>referral</referral_types>
        </open>
    </referral>
</case>"""
        check_xml_line_by_line(self, expected_response, response.content)
        
        
        
        