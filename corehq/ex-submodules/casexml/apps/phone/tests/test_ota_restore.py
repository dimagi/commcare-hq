from django.test import TestCase
import os
import time
from django.test.utils import override_settings
from couchforms.tests.testutils import post_xform_to_couch
from casexml.apps.case.models import CommCareCase
from casexml.apps.case.tests.util import check_xml_line_by_line, delete_all_cases, delete_all_sync_logs
from casexml.apps.case import process_cases
from datetime import datetime, date
from casexml.apps.phone.models import User, SyncLog
from casexml.apps.phone import xml, views
from django.contrib.auth.models import User as DjangoUser
from casexml.apps.phone.restore import generate_restore_payload
from django.http import HttpRequest
from casexml.apps.phone.tests import const
from casexml.apps.case import const as case_const
from casexml.apps.phone.tests.dummy import dummy_restore_xml, dummy_user,\
    dummy_user_xml


@override_settings(CASEXML_FORCE_DOMAIN_CHECK=False)
class OtaRestoreTest(TestCase):
    """Tests OTA Restore"""

    def setUp(self):
        delete_all_cases()
        delete_all_sync_logs()

    def testFromDjangoUser(self):
        django_user = DjangoUser(username="foo", password="secret", date_joined=datetime(2011, 6, 9))
        django_user.save()
        user = User.from_django_user(django_user)
        self.assertEqual(str(django_user.pk), user.user_id)
        self.assertEqual("foo", user.username)
        self.assertEqual("secret", user.password)
        self.assertEqual(datetime(2011, 6, 9), user.date_joined)
        self.assertFalse(bool(user.user_data))

    def testRegistrationXML(self):
        check_xml_line_by_line(self, dummy_user_xml(),
                               xml.get_registration_xml(dummy_user()))

    def testUserRestore(self):
        self.assertEqual(0, SyncLog.view(
            "phone/sync_logs_by_user",
            include_docs=True,
            reduce=False,
        ).count())
        restore_payload = generate_restore_payload(dummy_user(), items=True)
        sync_log = SyncLog.view(
            "phone/sync_logs_by_user",
            include_docs=True,
            reduce=False,
        ).one()
        check_xml_line_by_line(
            self,
            dummy_restore_xml(sync_log.get_id, items=3),
            restore_payload,
        )

    def testUserRestoreWithCase(self):
        file_path = os.path.join(os.path.dirname(__file__),
                                 "data", "create_short.xml")
        with open(file_path, "rb") as f:
            xml_data = f.read()
        form = post_xform_to_couch(xml_data)
        process_cases(form)
        user = dummy_user()

        # implicit length assertion
        [newcase] = CommCareCase.view("case/by_user", reduce=False, include_docs=True).all()
        self.assertEqual(1, len(user.get_case_updates(None).actual_cases_to_sync))
        expected_case_block = """
        <case>
            <case_id>asdf</case_id>
            <date_modified>2010-06-29T13:42:50Z</date_modified>
            <create>
                <case_type_id>test_case_type</case_type_id>
                <user_id>foo</user_id>
                <case_name>test case name</case_name>
                <external_id>someexternal</external_id>
            </create>
        </case>"""
        check_xml_line_by_line(self, expected_case_block, xml.get_case_xml(newcase, [case_const.CASE_ACTION_CREATE,
                                                                                     case_const.CASE_ACTION_UPDATE]))

        # check v2
        expected_v2_case_block = """
        <case case_id="asdf" date_modified="2010-06-29T13:42:50Z" user_id="foo" xmlns="http://commcarehq.org/case/transaction/v2" >
            <create>
                <case_type>test_case_type</case_type> 
                <case_name>test case name</case_name>
                <owner_id>foo</owner_id>
            </create>
            <update>
                <external_id>someexternal</external_id>
            </update>
        </case>"""
        check_xml_line_by_line(
            self,
            expected_v2_case_block,
            xml.get_case_xml(
                newcase,
                [case_const.CASE_ACTION_CREATE, case_const.CASE_ACTION_UPDATE],
                version="2.0",
            ),
        )

        restore_payload = generate_restore_payload(
            user=dummy_user(),
            items=True,
        )
        sync_log_id = SyncLog.view(
            "phone/sync_logs_by_user",
            include_docs=True,
            reduce=False,
        ).one().get_id
        check_xml_line_by_line(
            self,
            dummy_restore_xml(sync_log_id, expected_case_block, items=4),
            restore_payload
        )

    def testWithReferrals(self):
        self.assertEqual(0, CommCareCase.view(
            "case/by_user",
            reduce=False,
            include_docs=True,
        ).count())
        file_path = os.path.join(os.path.dirname(__file__),
                                 "data", "case_create.xml")
        with open(file_path, "rb") as f:
            xml_data = f.read()
        form = post_xform_to_couch(xml_data)
        process_cases(form)
        newcase = CommCareCase.view(
            "case/by_user",
            reduce=False,
            include_docs=True,
        ).one()
        self.assertEqual(0, len(newcase.referrals))
        file_path = os.path.join(os.path.dirname(__file__),
                                 "data", "case_refer.xml")
        with open(file_path, "rb") as f:
            xml_data = f.read()
        form = post_xform_to_couch(xml_data)
        process_cases(form)
        [updated_case] = CommCareCase.view("case/by_user", reduce=False, include_docs=True).all()
        self.assertEqual(1, len(updated_case.referrals))
        response = views.xml_for_case(HttpRequest(), updated_case.get_id)
        expected_response = """<case>
    <case_id>IKA9G79J4HDSPJLG3ER2OHQUY</case_id> 
    <date_modified>2011-02-19T16:46:28Z</date_modified>
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
       <request_timestamp>2011-02-19T16:46:28Z</request_timestamp>
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

        # this is really ridiculous. TODO, get rid of massive text wall x 2
        expected_v2_response = """<case xmlns="http://commcarehq.org/case/transaction/v2" case_id="IKA9G79J4HDSPJLG3ER2OHQUY" date_modified="2011-02-19T16:46:28Z" user_id="ae179a62-38af-11e0-b6a3-005056aa7fb5">
    <create>
        <case_type>cc_mobilize_client</case_type> 
        <case_name>SIEGEL-ROBERT-5412366523984</case_name>
        <owner_id>ae179a62-38af-11e0-b6a3-005056aa7fb5</owner_id>
    </create>
    <update>
       <external_id>5412366523984</external_id>
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
       <request_timestamp>2011-02-19T16:46:28Z</request_timestamp>
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
</case>"""

        v2response = views.xml_for_case(HttpRequest(), updated_case.get_id,
                                        version="2.0")
        check_xml_line_by_line(self, expected_v2_response, v2response.content)

    def testSyncTokenWithItems(self):
        self._test_sync_token(items=True)

    def testSyncTokenWithoutItems(self):
        self._test_sync_token(items=False)

    def _test_sync_token(self, items):
        """
        Tests sync token / sync mode support
        """
        file_path = os.path.join(os.path.dirname(__file__),
                                 "data", "create_short.xml")
        with open(file_path, "rb") as f:
            xml_data = f.read()
        form = post_xform_to_couch(xml_data)
        process_cases(form)

        time.sleep(1)
        restore_payload = generate_restore_payload(dummy_user(), items=items)

        sync_log_id = SyncLog.view(
            "phone/sync_logs_by_user",
            include_docs=True,
            reduce=False
        ).one().get_id
        expected_restore_payload = dummy_restore_xml(
            sync_log_id,
            const.CREATE_SHORT,
            items=4 if items else None,
        )
        check_xml_line_by_line(self, expected_restore_payload, restore_payload)

        time.sleep(1)
        sync_restore_payload = generate_restore_payload(
            user=dummy_user(),
            restore_id=sync_log_id,
            items=items,
        )
        all_sync_logs = SyncLog.view(
            "phone/sync_logs_by_user",
            include_docs=True,
            reduce=False,
        ).all()
        [latest_log] = [log for log in all_sync_logs
                        if log.get_id != sync_log_id]

        # should no longer have a case block in the restore XML
        check_xml_line_by_line(
            self,
            dummy_restore_xml(latest_log.get_id, items=3 if items else None),
            sync_restore_payload,
        )

        # apply an update
        time.sleep(1)
        file_path = os.path.join(os.path.dirname(__file__),
                                 "data", "update_short.xml")
        with open(file_path, "rb") as f:
            xml_data = f.read()
        form = post_xform_to_couch(xml_data)
        process_cases(form)

        time.sleep(1)
        sync_restore_payload = generate_restore_payload(
            user=dummy_user(),
            restore_id=latest_log.get_id,
            items=items,
        )
        all_sync_logs = SyncLog.view(
            "phone/sync_logs_by_user",
            include_docs=True,
            reduce=False,
        ).all()
        [even_latest_log] = [log for log in all_sync_logs
                             if log.get_id != sync_log_id and
                             log.get_id != latest_log.get_id]

        # case block should come back
        expected_sync_restore_payload = dummy_restore_xml(
            even_latest_log.get_id,
            const.UPDATE_SHORT,
            items=4 if items else None,
        )
        check_xml_line_by_line(self, expected_sync_restore_payload,
                               sync_restore_payload)

    def testRestoreAttributes(self):
        file_path = os.path.join(os.path.dirname(__file__),
                                 "data", "attributes.xml")
        with open(file_path, "rb") as f:
            xml_data = f.read()
        form = post_xform_to_couch(xml_data)
        process_cases(form)
        
        [newcase] = CommCareCase.view("case/by_user", reduce=False, include_docs=True).all()
        self.assertTrue(isinstance(newcase.adate, dict))
        self.assertEqual(date(2012,02,01), newcase.adate["#text"])
        self.assertEqual("i am an attribute", newcase.adate["@someattr"])
        self.assertTrue(isinstance(newcase.dateattr, dict))
        self.assertEqual("this shouldn't break", newcase.dateattr["#text"])
        self.assertEqual(date(2012,01,01), newcase.dateattr["@somedate"])
        self.assertTrue(isinstance(newcase.stringattr, dict))
        self.assertEqual("neither should this", newcase.stringattr["#text"])
        self.assertEqual("i am a string", newcase.stringattr["@somestring"])
        restore_payload = generate_restore_payload(dummy_user())
        # ghetto
        self.assertTrue('<dateattr somedate="2012-01-01">' in restore_payload)
        self.assertTrue('<stringattr somestring="i am a string">' in restore_payload)
