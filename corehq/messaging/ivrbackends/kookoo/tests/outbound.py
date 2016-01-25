from casexml.apps.case.models import CommCareCase
from corehq.apps.domain.models import Domain
from corehq.apps.sms.tests.util import TouchformsTestCase
from corehq.apps.sms.mixin import MobileBackend
from corehq.apps.sms.models import CallLog
from corehq.apps.sms.util import register_sms_contact
from corehq.apps.reminders.models import (CaseReminderHandler,
    METHOD_IVR_SURVEY, RECIPIENT_CASE, REMINDER_TYPE_DEFAULT,
    CASE_CRITERIA, CaseReminderEvent, FIRE_TIME_DEFAULT,
    EVENT_AS_SCHEDULE, MATCH_EXACT, RECIPIENT_OWNER)
from corehq.messaging.ivrbackends.kookoo.models import KooKooBackend
from mock import patch
from time import sleep
from datetime import datetime, time
import hashlib
import os
import urllib
import urllib2


def mock_kookoo_outbound_api(*args, **kwargs):
    session_id = hashlib.sha224(datetime.utcnow().isoformat()).hexdigest()
    return "<request><status>queued</status><message>%s</message></request>" % session_id


@patch('corehq.messaging.ivrbackends.kookoo.models.SQLKooKooBackend.invoke_kookoo_outbound_api',
    new=mock_kookoo_outbound_api)
class KooKooTestCase(TouchformsTestCase):
    """
    Must be run manually (see corehq.apps.sms.tests.util.TouchformsTestCase)
    """

    def setUp(self):
        super(KooKooTestCase, self).setUp()
        self.ivr_backend = KooKooBackend(
            _id="MOBILE_BACKEND_KOOKOO",
            name="MOBILE_BACKEND_KOOKOO",
            is_global=True,
            api_key="xyz",
        )
        self.ivr_backend.save()

        self.user1 = self.create_mobile_worker("user1", "123", "91001", save_vn=False)
        self.user2 = self.create_mobile_worker("user2", "123", "91002", save_vn=False)
        self.create_group("group1", [self.user1, self.user2])

        dirname = os.path.dirname(os.path.abspath(__file__))
        self.load_app("app1.json", dirname)
        self.load_app("app2.json", dirname)

        self.reminder1 = CaseReminderHandler(
            domain=self.domain,
            active=True,
            case_type="participant",
            method=METHOD_IVR_SURVEY,
            recipient=RECIPIENT_CASE,
            sample_id=None,
            user_group_id=None,
            user_id=None,
            case_id=None,
            reminder_type=REMINDER_TYPE_DEFAULT,
            submit_partial_forms=True,
            include_case_side_effects=False,
            max_question_retries=5,
            start_condition_type=CASE_CRITERIA,
            start_property="name",
            start_value="case1",
            start_date=None,
            start_offset=0,
            start_match_type=MATCH_EXACT,
            events=[
                CaseReminderEvent(
                    day_num=0,
                    fire_time=time(12,0),
                    fire_time_type=FIRE_TIME_DEFAULT,
                    callback_timeout_intervals=[30],
                    form_unique_id=self.apps[0].modules[0].forms[0].unique_id,
                ),
                CaseReminderEvent(
                    day_num=0,
                    fire_time=time(13,0),
                    fire_time_type=FIRE_TIME_DEFAULT,
                    callback_timeout_intervals=[30],
                    form_unique_id=self.apps[0].modules[0].forms[1].unique_id,
                ),
            ],
            schedule_length=1,
            event_interpretation=EVENT_AS_SCHEDULE,
            max_iteration_count=7,
            until=None,
            force_surveys_to_use_triggered_case=False,
        )
        self.reminder1.save()

        self.reminder2 = CaseReminderHandler(
            domain=self.domain,
            active=True,
            case_type="participant",
            method=METHOD_IVR_SURVEY,
            recipient=RECIPIENT_OWNER,
            sample_id=None,
            user_group_id=None,
            user_id=None,
            case_id=None,
            reminder_type=REMINDER_TYPE_DEFAULT,
            submit_partial_forms=True,
            include_case_side_effects=True,
            max_question_retries=5,
            start_condition_type=CASE_CRITERIA,
            start_property="name",
            start_value="case2",
            start_date=None,
            start_offset=0,
            start_match_type=MATCH_EXACT,
            events=[
                CaseReminderEvent(
                    day_num=0,
                    fire_time=time(12,0),
                    fire_time_type=FIRE_TIME_DEFAULT,
                    callback_timeout_intervals=[30, 30],
                    form_unique_id=self.apps[1].modules[0].forms[0].unique_id,
                ),
            ],
            schedule_length=1,
            event_interpretation=EVENT_AS_SCHEDULE,
            max_iteration_count=7,
            until=None,
            force_surveys_to_use_triggered_case=False,
        )
        self.reminder2.save()

    def kookoo_in(self, params):
        """
        params should be a dictionary containing:
        event, cid, sid, and (optionally) data
        """
        params = urllib.urlencode(params)
        url = "%s/kookoo/ivr/" % self.live_server_url
        return urllib2.urlopen("%s?%s" % (url, params)).read()

    def kookoo_finished(self, params):
        """
        params should be a dictionary containing:
        sid, status, and duration
        """
        params = urllib.urlencode(params)
        url = "%s/kookoo/ivr_finished/" % self.live_server_url
        return urllib2.urlopen(url, params).read()

    def testOutbound(self):
        # Send an outbound call using self.reminder1 to self.case
        # and answer it
        CaseReminderHandler.now = datetime(2014, 6, 23, 10, 0)
        self.case = CommCareCase.get(register_sms_contact(
            self.domain,
            'participant',
            'case1',
            self.user1._id,
            '91000',
            owner_id=self.groups[0]._id,
            contact_ivr_backend_id='MOBILE_BACKEND_KOOKOO'
        ))
        CaseReminderHandler.now = datetime(2014, 6, 23, 12, 0)
        CaseReminderHandler.fire_reminders()
        reminder = self.reminder1.get_reminder(self.case)
        self.assertEquals(reminder.next_fire, datetime(2014, 6, 23, 12, 30))

        call = self.get_last_outbound_call(self.case)
        self.assertTrue(call.use_precached_first_response)

        kookoo_session_id = call.gateway_session_id[7:]
        resp = self.kookoo_in({
            "cid": "0000",
            "sid": kookoo_session_id,
            "event": "NewCall",
        })
        self.assertEqual(resp, '<response sid="%s"><collectdtmf l="1" o="3000">'
            '<playtext>How do you feel today? Press 1 for good, 2 for bad.'
            '</playtext></collectdtmf></response>' % kookoo_session_id)

        resp = self.kookoo_in({
            "cid": "0000",
            "sid": kookoo_session_id,
            "event": "GotDTMF",
            "data": "1",
        })
        self.assertEqual(resp, '<response sid="%s"><collectdtmf l="1" o="3000">'
            '<playtext>Did you remember to take your meds today? Press 1 for yes, 2 for no.'
            '</playtext></collectdtmf></response>' % kookoo_session_id)

        resp = self.kookoo_in({
            "cid": "0000",
            "sid": kookoo_session_id,
            "event": "GotDTMF",
            "data": "2",
        })
        self.assertEqual(resp, '<response sid="%s"><hangup/></response>' % kookoo_session_id)

        self.kookoo_finished({
            "sid": kookoo_session_id,
            "status": "answered",
            "duration": "20",
        })

        call = CallLog.get(call._id)
        self.assertTrue(call.answered)
        self.assertEqual(call.duration, 20)

        form = self.get_last_form_submission()
        self.assertFormQuestionEquals(form, "how_feel", "1")
        self.assertFormQuestionEquals(form, "take_meds", "2")
        case = CommCareCase.get(self.case._id)
        self.assertCasePropertyEquals(case, "how_feel", "1")
        self.assertCasePropertyEquals(case, "take_meds", "2")

        CaseReminderHandler.now = datetime(2014, 6, 23, 12, 30)
        CaseReminderHandler.fire_reminders()

        reminder = self.reminder1.get_reminder(self.case)
        self.assertEquals(reminder.next_fire, datetime(2014, 6, 23, 13, 0))

        last_call = self.get_last_outbound_call(self.case)
        self.assertEqual(call._id, last_call._id)

        # Move on to the second event which now uses an all-label form and
        # should not precache the first ivr response
        CaseReminderHandler.now = datetime(2014, 6, 23, 13, 0)
        CaseReminderHandler.fire_reminders()

        reminder = self.reminder1.get_reminder(self.case)
        self.assertEquals(reminder.next_fire, datetime(2014, 6, 23, 13, 30))

        call = self.get_last_outbound_call(self.case)
        self.assertFalse(call.use_precached_first_response)

        kookoo_session_id = call.gateway_session_id[7:]
        resp = self.kookoo_in({
            "cid": "0000",
            "sid": kookoo_session_id,
            "event": "NewCall",
        })
        self.assertEqual(resp, '<response sid="%s">'
            '<playtext>This is just a reminder to take your meds.'
            '</playtext><hangup/></response>' % kookoo_session_id)

        self.kookoo_finished({
            "sid": kookoo_session_id,
            "status": "answered",
            "duration": "5",
        })

        call = CallLog.get(call._id)
        self.assertTrue(call.answered)
        self.assertEqual(call.duration, 5)

        form = self.get_last_form_submission()
        self.assertFormQuestionEquals(form, "label", "ok")

        CaseReminderHandler.now = datetime(2014, 6, 23, 13, 30)
        CaseReminderHandler.fire_reminders()

        reminder = self.reminder1.get_reminder(self.case)
        self.assertEquals(reminder.next_fire, datetime(2014, 6, 24, 12, 0))

        last_call = self.get_last_outbound_call(self.case)
        self.assertEqual(call._id, last_call._id)

        # Now test sending outbound calls to a group of users (the owners
        # of the case)

        # Allow sending to unverified numbers
        self.domain_obj = Domain.get(self.domain_obj._id)
        self.domain_obj.send_to_duplicated_case_numbers = True
        self.domain_obj.save()

        CaseReminderHandler.now = datetime(2014, 6, 24, 10, 0)
        self.case = CommCareCase.get(register_sms_contact(
            self.domain,
            'participant',
            'case2',
            self.user1._id,
            '91003',
            owner_id=self.groups[0]._id,
        ))
        reminder = self.reminder2.get_reminder(self.case)
        self.assertEquals(reminder.next_fire, datetime(2014, 6, 24, 12, 0))

        CaseReminderHandler.now = datetime(2014, 6, 24, 12, 0)
        CaseReminderHandler.fire_reminders()
        reminder = self.reminder2.get_reminder(self.case)
        self.assertEquals(reminder.next_fire, datetime(2014, 6, 24, 12, 30))

        call1 = self.get_last_outbound_call(self.user1)
        self.assertTrue(call1.use_precached_first_response)
        self.assertFalse(call1.answered)

        call2 = self.get_last_outbound_call(self.user2)
        self.assertTrue(call2.use_precached_first_response)
        self.assertFalse(call2.answered)

        old_call1 = call1
        old_call2 = call2

        CaseReminderHandler.now = datetime(2014, 6, 24, 12, 30)
        CaseReminderHandler.fire_reminders()
        reminder = self.reminder2.get_reminder(self.case)
        self.assertEquals(reminder.next_fire, datetime(2014, 6, 24, 13, 0))

        call1 = self.get_last_outbound_call(self.user1)
        self.assertTrue(call1.use_precached_first_response)
        self.assertNotEqual(call1._id, old_call1._id)

        call2 = self.get_last_outbound_call(self.user2)
        self.assertTrue(call2.use_precached_first_response)
        self.assertFalse(call2.answered)
        self.assertNotEqual(call2._id, old_call2._id)

        kookoo_session_id = call1.gateway_session_id[7:]
        resp = self.kookoo_in({
            "cid": "0001",
            "sid": kookoo_session_id,
            "event": "NewCall",
        })
        self.assertEqual(resp, '<response sid="%s"><collectdtmf l="1" o="3000">'
            '<playtext>How do you feel today? Press 1 for good, 2 for bad.'
            '</playtext></collectdtmf></response>' % kookoo_session_id)

        resp = self.kookoo_in({
            "cid": "0001",
            "sid": kookoo_session_id,
            "event": "GotDTMF",
            "data": "2",
        })
        self.assertEqual(resp, '<response sid="%s"><collectdtmf l="1" o="3000">'
            '<playtext>Did you remember to take your meds today? Press 1 for yes, 2 for no.'
            '</playtext></collectdtmf></response>' % kookoo_session_id)

        resp = self.kookoo_in({
            "cid": "0001",
            "sid": kookoo_session_id,
            "event": "GotDTMF",
            "data": "1",
        })
        self.assertEqual(resp, '<response sid="%s"><hangup/></response>' % kookoo_session_id)

        self.kookoo_finished({
            "sid": kookoo_session_id,
            "status": "answered",
            "duration": "20",
        })
        call1 = CallLog.get(call1._id)
        self.assertTrue(call1.answered)
        self.assertEqual(call1.duration, 20)

        form = self.get_last_form_submission()
        self.assertFormQuestionEquals(form, "how_feel", "2")
        self.assertFormQuestionEquals(form, "take_meds", "1")
        self.assertEqual(form.form["meta"]["userID"], self.user1._id)
        case = CommCareCase.get(self.case._id)
        self.assertCasePropertyEquals(case, "how_feel", "2")
        self.assertCasePropertyEquals(case, "take_meds", "1")
        self.assertEqual(case.user_id, self.user1._id)

        old_call1 = call1
        old_call2 = call2

        CaseReminderHandler.now = datetime(2014, 6, 24, 13, 0)
        CaseReminderHandler.fire_reminders()
        reminder = self.reminder2.get_reminder(self.case)
        self.assertEquals(reminder.next_fire, datetime(2014, 6, 25, 12, 0))

        call1 = self.get_last_outbound_call(self.user1)
        # No new call for user1 since it was already answered
        self.assertEqual(call1._id, old_call1._id)

        call2 = self.get_last_outbound_call(self.user2)
        self.assertTrue(call2.use_precached_first_response)
        self.assertNotEqual(call2._id, old_call2._id)

        kookoo_session_id = call2.gateway_session_id[7:]
        resp = self.kookoo_in({
            "cid": "0002",
            "sid": kookoo_session_id,
            "event": "NewCall",
        })
        self.assertEqual(resp, '<response sid="%s"><collectdtmf l="1" o="3000">'
            '<playtext>How do you feel today? Press 1 for good, 2 for bad.'
            '</playtext></collectdtmf></response>' % kookoo_session_id)

        resp = self.kookoo_in({
            "cid": "0002",
            "sid": kookoo_session_id,
            "event": "GotDTMF",
            "data": "1",
        })
        self.assertEqual(resp, '<response sid="%s"><collectdtmf l="1" o="3000">'
            '<playtext>Did you remember to take your meds today? Press 1 for yes, 2 for no.'
            '</playtext></collectdtmf></response>' % kookoo_session_id)

        resp = self.kookoo_in({
            "cid": "0002",
            "sid": kookoo_session_id,
            "event": "GotDTMF",
            "data": "2",
        })
        self.assertEqual(resp, '<response sid="%s"><hangup/></response>' % kookoo_session_id)

        self.kookoo_finished({
            "sid": kookoo_session_id,
            "status": "answered",
            "duration": "20",
        })
        call2 = CallLog.get(call2._id)
        self.assertTrue(call2.answered)
        self.assertEqual(call2.duration, 20)

        form = self.get_last_form_submission()
        self.assertFormQuestionEquals(form, "how_feel", "1")
        self.assertFormQuestionEquals(form, "take_meds", "2")
        self.assertEqual(form.form["meta"]["userID"], self.user2._id)
        case = CommCareCase.get(self.case._id)
        self.assertCasePropertyEquals(case, "how_feel", "1")
        self.assertCasePropertyEquals(case, "take_meds", "2")
        self.assertEqual(case.user_id, self.user2._id)

    def tearDown(self):
        self.ivr_backend.delete()
        super(KooKooTestCase, self).tearDown()


