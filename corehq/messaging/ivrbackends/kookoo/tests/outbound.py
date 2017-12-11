from __future__ import absolute_import
from corehq.apps.domain.models import Domain
from corehq.apps.ivr.models import Call
from corehq.apps.sms.tests.util import TouchformsTestCase
from corehq.apps.sms.util import register_sms_contact
from corehq.apps.reminders.models import (CaseReminderHandler,
    CaseReminderEvent, FIRE_TIME_DEFAULT,
    EVENT_AS_SCHEDULE, MATCH_EXACT)
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from corehq.form_processor.tests.utils import run_with_all_backends, FormProcessorTestUtils
from corehq.messaging.ivrbackends.kookoo.models import SQLKooKooBackend
from mock import patch
from datetime import datetime, time
import hashlib
import os
import six.moves.urllib.request, six.moves.urllib.parse, six.moves.urllib.error
import six.moves.urllib.request, six.moves.urllib.error, six.moves.urllib.parse


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
        self.ivr_backend = SQLKooKooBackend(
            backend_type=SQLKooKooBackend.IVR,
            name="MOBILE_BACKEND_KOOKOO",
            is_global=True,
            hq_api_id=SQLKooKooBackend.get_api_id()
        )
        self.ivr_backend.set_extra_fields(api_key="xyz")
        self.ivr_backend.save()

        self.user1 = self.create_mobile_worker("user1", "123", "91001", save_vn=False)
        self.user2 = self.create_mobile_worker("user2", "123", "91002", save_vn=False)
        self.create_group("group1", [self.user1, self.user2])

        dirname = os.path.dirname(os.path.abspath(__file__))
        self.load_app("app1.json", dirname)
        self.load_app("app2.json", dirname)

        self.reminder1 = (CaseReminderHandler
            .create(self.domain, 'test1')
            .set_case_criteria_start_condition('participant', 'name', MATCH_EXACT, 'case1')
            .set_case_criteria_start_date()
            .set_case_recipient()
            .set_ivr_survey_content_type()
            .set_schedule_manually(EVENT_AS_SCHEDULE, 1, [
                CaseReminderEvent(
                    day_num=0,
                    fire_time=time(12, 0),
                    fire_time_type=FIRE_TIME_DEFAULT,
                    callback_timeout_intervals=[30],
                    form_unique_id=self.apps[0].modules[0].forms[0].unique_id,
                ),
                CaseReminderEvent(
                    day_num=0,
                    fire_time=time(13, 0),
                    fire_time_type=FIRE_TIME_DEFAULT,
                    callback_timeout_intervals=[30],
                    form_unique_id=self.apps[0].modules[0].forms[1].unique_id,
                ),
            ]).set_stop_condition(max_iteration_count=7)
            .set_advanced_options(submit_partial_forms=True, max_question_retries=5))
        self.reminder1.save()

        self.reminder2 = (CaseReminderHandler
            .create(self.domain, 'test2')
            .set_case_criteria_start_condition('participant', 'name', MATCH_EXACT, 'case2')
            .set_case_criteria_start_date()
            .set_case_owner_recipient()
            .set_ivr_survey_content_type()
            .set_daily_schedule(fire_time=time(12, 0), timeouts=[30, 30],
                form_unique_id=self.apps[1].modules[0].forms[0].unique_id)
            .set_stop_condition(max_iteration_count=7)
            .set_advanced_options(submit_partial_forms=True, include_case_side_effects=True,
                max_question_retries=5))
        self.reminder2.save()

    def kookoo_in(self, params):
        """
        params should be a dictionary containing:
        event, cid, sid, and (optionally) data
        """
        params = six.moves.urllib.parse.urlencode(params)
        url = "%s/kookoo/ivr/" % self.live_server_url
        return six.moves.urllib.request.urlopen("%s?%s" % (url, params)).read()

    def kookoo_finished(self, params):
        """
        params should be a dictionary containing:
        sid, status, and duration
        """
        params = six.moves.urllib.parse.urlencode(params)
        url = "%s/kookoo/ivr_finished/" % self.live_server_url
        return six.moves.urllib.request.urlopen(url, params).read()

    @run_with_all_backends
    def testOutbound(self):
        # Send an outbound call using self.reminder1 to self.case
        # and answer it
        CaseReminderHandler.now = datetime(2014, 6, 23, 10, 0)
        self.case = CaseAccessors(self.domain).get_case(register_sms_contact(
            self.domain,
            'participant',
            'case1',
            self.user1.get_id,
            '91000',
            owner_id=self.groups[0].get_id,
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

        call = Call.objects.get(pk=call.pk)
        self.assertTrue(call.answered)
        self.assertEqual(call.duration, 20)

        form = self.get_last_form_submission()
        self.assertFormQuestionEquals(form, "how_feel", "1")
        self.assertFormQuestionEquals(form, "take_meds", "2")
        case = CaseAccessors(self.domain).get_case(self.case.case_id)
        self.assertCasePropertyEquals(case, "how_feel", "1")
        self.assertCasePropertyEquals(case, "take_meds", "2")

        CaseReminderHandler.now = datetime(2014, 6, 23, 12, 30)
        CaseReminderHandler.fire_reminders()

        reminder = self.reminder1.get_reminder(self.case)
        self.assertEquals(reminder.next_fire, datetime(2014, 6, 23, 13, 0))

        last_call = self.get_last_outbound_call(self.case)
        self.assertEqual(call.pk, last_call.pk)

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

        call = Call.objects.get(pk=call.pk)
        self.assertTrue(call.answered)
        self.assertEqual(call.duration, 5)

        form = self.get_last_form_submission()
        self.assertFormQuestionEquals(form, "label", "ok")

        CaseReminderHandler.now = datetime(2014, 6, 23, 13, 30)
        CaseReminderHandler.fire_reminders()

        reminder = self.reminder1.get_reminder(self.case)
        self.assertEquals(reminder.next_fire, datetime(2014, 6, 24, 12, 0))

        last_call = self.get_last_outbound_call(self.case)
        self.assertEqual(call.pk, last_call.pk)

        # Now test sending outbound calls to a group of users (the owners
        # of the case)

        # Allow sending to unverified numbers
        self.domain_obj = Domain.get(self.domain_obj.get_id)
        self.domain_obj.send_to_duplicated_case_numbers = True
        self.domain_obj.save()

        CaseReminderHandler.now = datetime(2014, 6, 24, 10, 0)
        self.case = CaseAccessors(self.domain).get_case(register_sms_contact(
            self.domain,
            'participant',
            'case2',
            self.user1.get_id,
            '91003',
            owner_id=self.groups[0].get_id,
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
        self.assertNotEqual(call1.pk, old_call1.pk)

        call2 = self.get_last_outbound_call(self.user2)
        self.assertTrue(call2.use_precached_first_response)
        self.assertFalse(call2.answered)
        self.assertNotEqual(call2.pk, old_call2.pk)

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
        call1 = Call.objects.get(pk=call1.pk)
        self.assertTrue(call1.answered)
        self.assertEqual(call1.duration, 20)

        form = self.get_last_form_submission()
        self.assertFormQuestionEquals(form, "how_feel", "2")
        self.assertFormQuestionEquals(form, "take_meds", "1")
        self.assertEqual(form.form_data["meta"]["userID"], self.user1.get_id)
        case = CaseAccessors(self.domain).get_case(self.case.case_id)
        self.assertCasePropertyEquals(case, "how_feel", "2")
        self.assertCasePropertyEquals(case, "take_meds", "1")
        self.assertEqual(case.user_id, self.user1.get_id)

        old_call1 = call1
        old_call2 = call2

        CaseReminderHandler.now = datetime(2014, 6, 24, 13, 0)
        CaseReminderHandler.fire_reminders()
        reminder = self.reminder2.get_reminder(self.case)
        self.assertEquals(reminder.next_fire, datetime(2014, 6, 25, 12, 0))

        call1 = self.get_last_outbound_call(self.user1)
        # No new call for user1 since it was already answered
        self.assertEqual(call1.pk, old_call1.pk)

        call2 = self.get_last_outbound_call(self.user2)
        self.assertTrue(call2.use_precached_first_response)
        self.assertNotEqual(call2.pk, old_call2.pk)

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
        call2 = Call.objects.get(pk=call2.pk)
        self.assertTrue(call2.answered)
        self.assertEqual(call2.duration, 20)

        form = self.get_last_form_submission()
        self.assertFormQuestionEquals(form, "how_feel", "1")
        self.assertFormQuestionEquals(form, "take_meds", "2")
        self.assertEqual(form.form_data["meta"]["userID"], self.user2.get_id)
        case = CaseAccessors(self.domain).get_case(self.case.case_id)
        self.assertCasePropertyEquals(case, "how_feel", "1")
        self.assertCasePropertyEquals(case, "take_meds", "2")
        self.assertEqual(case.user_id, self.user2.get_id)

    def tearDown(self):
        FormProcessorTestUtils.delete_all_cases(self.domain)
        self.ivr_backend.delete()
        super(KooKooTestCase, self).tearDown()
