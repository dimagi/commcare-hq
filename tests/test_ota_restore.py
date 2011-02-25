from django.test import TestCase
import os
from couchforms.util import post_xform_to_couch
from corehq.apps.case.models.couch import CommCareCase
from django.test.client import Client
from django.core.urlresolvers import reverse
from corehq.apps.case.tests.util import check_xml_line_by_line

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
        [newcase] = CommCareCase.view("case/by_xform_id", include_docs=True).all()
        self.assertEqual(0, len(newcase.referrals))
        file_path = os.path.join(os.path.dirname(__file__), "data", "case_refer.xml")
        with open(file_path, "rb") as f:
            xml_data = f.read()
        form = post_xform_to_couch(xml_data)
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
        <muscleweakness></muscleweakness>
        <tb_lasttreatment></tb_lasttreatment>
        <surname>SIEGEL</surname>
        <staffnumber1></staffnumber1>
        <deafness></deafness>
        <contact_phone_alt></contact_phone_alt>
        <sleeping></sleeping>
        <txoutcome></txoutcome>
        <abdominalpain></abdominalpain>
        <staffnumber3></staffnumber3>
        <staffnumber2></staffnumber2>
        <arv_taking></arv_taking>
        <arv_lasttreatment></arv_lasttreatment>
        <depression></depression>
        <ringing></ringing>
        <tingling></tingling>
        <tribal_area></tribal_area>
        <short_name>SIEGEL, ROBERT</short_name>
        <request_name>ME</request_name>
        <patient_dot>123</patient_dot>
        <assistance></assistance>
        <diarrhea></diarrhea>
        <Problems></Problems>
        <rash></rash>
        <other></other>
        <given_name>ROBERT</given_name>
        <swelling></swelling>
        <tbtype></tbtype>
        <request_reason></request_reason>
        <imbalance></imbalance>
        <phone_number>1</phone_number>
        <seizures></seizures>
        <allmeds_likert></allmeds_likert>
        <txstart>2011-02-11</txstart>
        <request_rank>staff_nurse</request_rank>
        <confusion></confusion>
        <injectionother></injectionother>
        <contact_name_alt></contact_name_alt>
        <vomiting></vomiting>
        <tb_missedtreatments></tb_missedtreatments>
        <jointpain></jointpain>
        <injectiontype></injectiontype>
        <address></address>
        <contact_age_alt></contact_age_alt>
        <nickname>BOB</nickname>
        <legal_name>ROBERT SIEGEL</legal_name>
        <musclepain></musclepain>
        <addstaff2></addstaff2>
        <request_timestamp>2011-02-19 16:46:28</request_timestamp>
        <dob>2011-02-11</dob>
        <gender>male</gender>
        <addstaff1></addstaff1>
        <psychosis></psychosis>
        <patient_id>5412366523984</patient_id>
        <place></place>
        <jaundice></jaundice>
        <arv_missedtreatments></arv_missedtreatments>
        <vision></vision>
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
        
        
        
        