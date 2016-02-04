from corehq.apps.ivr.models import Call
from corehq.apps.sms.models import (SMSLog, SMS, INCOMING, OUTGOING,
    MessagingEvent, MessagingSubEvent, CallLog)
from custom.fri.models import FRISMSLog, PROFILES
from datetime import datetime, timedelta
from django.test import TestCase
import random
import string
from time import sleep


class BaseMigrationTestCase(TestCase):
    def setUp(self):
        self.domain = 'test-sms-sql-migration'

    def deleteAllLogs(self):
        for smslog in SMSLog.view(
            'sms/by_domain',
            startkey=[self.domain, 'SMSLog'],
            endkey=[self.domain, 'SMSLog', {}],
            include_docs=True,
            reduce=False,
        ).all():
            smslog.delete()

        for callog in CallLog.view(
            'sms/by_domain',
            startkey=[self.domain, 'CallLog'],
            endkey=[self.domain, 'CallLog', {}],
            include_docs=True,
            reduce=False,
        ).all():
            callog.delete()

        SMS.objects.filter(domain=self.domain).delete()
        Call.objects.filter(domain=self.domain).delete()
        MessagingSubEvent.objects.filter(parent__domain=self.domain).delete()
        MessagingEvent.objects.filter(domain=self.domain).delete()

    def tearDown(self):
        self.deleteAllLogs()

    def randomDirection(self):
        return [INCOMING, OUTGOING][random.randint(0, 1)]

    def randomBoolean(self):
        return [True, False][random.randint(0, 1)]

    def randomString(self, length=10):
        return ''.join([random.choice(string.lowercase) for i in range(length)])

    def randomInteger(self, beginning=0, end=1000):
        return random.randint(beginning, end)

    def randomDateTime(self, max_lookback=500000):
        result = datetime.utcnow()
        result -= timedelta(minutes=random.randint(0, max_lookback))
        result = result.replace(microsecond=0)
        return result

    def randomRiskProfile(self):
        return random.choice(PROFILES)

    def randomMessagingSubEventId(self):
        # Just create a dummy event and subevent to generate
        # a valid MessagingSubEvent foreign key
        event = MessagingEvent(
            domain=self.domain,
            date=self.randomDateTime(),
            source=MessagingEvent.SOURCE_KEYWORD,
            content_type=MessagingEvent.CONTENT_SMS,
            status=MessagingEvent.STATUS_COMPLETED,
        )
        event.save()
        subevent = MessagingSubEvent(
            date=self.randomDateTime(),
            parent=event,
            recipient_type=MessagingEvent.RECIPIENT_CASE,
            content_type=MessagingEvent.CONTENT_SMS,
            status=MessagingEvent.STATUS_COMPLETED,
        )
        subevent.save()
        return subevent.pk

    def checkFieldValues(self, object1, object2, fields):
        for field_name in fields:
            value1 = getattr(object1, field_name)
            value2 = getattr(object2, field_name)
            self.assertIsNotNone(value1)
            self.assertIsNotNone(value2)
            self.assertEqual(value1, value2)


class SMSMigrationTestCase(BaseMigrationTestCase):
    def getSMSLogCount(self):
        result = SMSLog.view(
            'sms/by_domain',
            startkey=[self.domain, 'SMSLog'],
            endkey=[self.domain, 'SMSLog', {}],
            include_docs=False,
            reduce=True,
        ).all()
        if result:
            return result[0]['value']
        return 0

    def getSMSCount(self):
        return SMS.objects.filter(domain=self.domain).count()

    def setRandomSMSLogValues(self, smslog):
        smslog.couch_recipient_doc_type = self.randomString()
        smslog.couch_recipient = self.randomString()
        smslog.phone_number = self.randomString()
        smslog.direction = self.randomDirection()
        smslog.date = self.randomDateTime()
        smslog.domain = self.domain
        smslog.backend_api = self.randomString()
        smslog.backend_id = self.randomString()
        smslog.billed = self.randomBoolean()
        smslog.chat_user_id = self.randomString()
        smslog.workflow = self.randomString()
        smslog.xforms_session_couch_id = self.randomString()
        smslog.reminder_id = self.randomString()
        smslog.processed = self.randomBoolean()
        smslog.datetime_to_process = self.randomDateTime()
        smslog.num_processing_attempts = self.randomInteger()
        smslog.error = self.randomBoolean()
        smslog.system_error_message = self.randomString()
        smslog.domain_scope = self.randomString()
        smslog.queued_timestamp = self.randomDateTime()
        smslog.processed_timestamp = self.randomDateTime()
        smslog.system_phone_number = self.randomString()
        smslog.ignore_opt_out = self.randomBoolean()
        smslog.location_id = self.randomString()
        smslog.text = self.randomString()
        smslog.raw_text = self.randomString()
        smslog.backend_message_id = self.randomString()
        smslog.invalid_survey_response = self.randomBoolean()
        smslog.messaging_subevent_id = self.randomMessagingSubEventId()

    def setRandomFRISMSLogValues(self, frismslog):
        frismslog.fri_message_bank_lookup_completed = self.randomBoolean()
        frismslog.fri_message_bank_message_id = self.randomString()
        frismslog.fri_id = self.randomString()
        frismslog.fri_risk_profile = self.randomRiskProfile()

    def setRandomSMSValues(self, sms):
        sms.domain = self.domain
        sms.date = self.randomDateTime()
        sms.couch_recipient_doc_type = self.randomString()
        sms.couch_recipient = self.randomString()
        sms.phone_number = self.randomString()
        sms.direction = self.randomDirection()
        sms.text = self.randomString()
        sms.raw_text = self.randomString()
        sms.datetime_to_process = self.randomDateTime()
        sms.processed = self.randomBoolean()
        sms.num_processing_attempts = self.randomInteger()
        sms.queued_timestamp = self.randomDateTime()
        sms.processed_timestamp = self.randomDateTime()
        sms.error = self.randomBoolean()
        sms.system_error_message = self.randomString()
        sms.billed = self.randomBoolean()
        sms.domain_scope = self.randomString()
        sms.ignore_opt_out = self.randomBoolean()
        sms.backend_api = self.randomString()
        sms.backend_id = self.randomString()
        sms.system_phone_number = self.randomString()
        sms.backend_message_id = self.randomString()
        sms.workflow = self.randomString()
        sms.chat_user_id = self.randomString()
        sms.xforms_session_couch_id = self.randomString()
        sms.invalid_survey_response = self.randomBoolean()
        sms.reminder_id = self.randomString()
        sms.location_id = self.randomString()
        sms.fri_message_bank_lookup_completed = self.randomBoolean()
        sms.fri_message_bank_message_id = self.randomString()
        sms.fri_id = self.randomString()
        sms.fri_risk_profile = self.randomRiskProfile()
        sms.messaging_subevent_id = self.randomMessagingSubEventId()

    def testSMSLogSync(self):
        self.deleteAllLogs()
        self.assertEqual(self.getSMSLogCount(), 0)
        self.assertEqual(self.getSMSCount(), 0)

        # Test Create
        smslog = SMSLog()
        self.setRandomSMSLogValues(smslog)
        smslog.save()

        sleep(1)
        self.assertEqual(self.getSMSLogCount(), 1)
        self.assertEqual(self.getSMSCount(), 1)

        sms = SMS.objects.get(couch_id=smslog._id)
        self.checkFieldValues(smslog, sms, SMSLog._migration_get_fields())
        self.assertTrue(SMSLog.get_db().get_rev(smslog._id).startswith('1-'))

        # Test Update
        self.setRandomSMSLogValues(smslog)
        smslog.save()

        sleep(1)
        self.assertEqual(self.getSMSLogCount(), 1)
        self.assertEqual(self.getSMSCount(), 1)
        sms = SMS.objects.get(couch_id=smslog._id)
        self.checkFieldValues(smslog, sms, SMSLog._migration_get_fields())
        self.assertTrue(SMSLog.get_db().get_rev(smslog._id).startswith('2-'))

    def testFRISMSLogSync(self):
        self.deleteAllLogs()
        self.assertEqual(self.getSMSLogCount(), 0)
        self.assertEqual(self.getSMSCount(), 0)

        # Test Create
        smslog = SMSLog()
        self.setRandomSMSLogValues(smslog)
        smslog.save()

        sleep(1)
        smslog = FRISMSLog.get(smslog._id)
        self.setRandomFRISMSLogValues(smslog)
        smslog.save()

        sleep(1)
        self.assertEqual(self.getSMSLogCount(), 1)
        self.assertEqual(self.getSMSCount(), 1)

        sms = SMS.objects.get(couch_id=smslog._id)
        self.checkFieldValues(smslog, sms, FRISMSLog._migration_get_fields())
        self.assertTrue(FRISMSLog.get_db().get_rev(smslog._id).startswith('2-'))

        # Test Update
        self.setRandomSMSLogValues(smslog)
        self.setRandomFRISMSLogValues(smslog)
        smslog.save()

        sleep(1)
        self.assertEqual(self.getSMSLogCount(), 1)
        self.assertEqual(self.getSMSCount(), 1)
        sms = SMS.objects.get(couch_id=smslog._id)
        self.checkFieldValues(smslog, sms, FRISMSLog._migration_get_fields())
        self.assertTrue(SMSLog.get_db().get_rev(smslog._id).startswith('3-'))

    def testSMSSync(self):
        self.deleteAllLogs()
        self.assertEqual(self.getSMSLogCount(), 0)
        self.assertEqual(self.getSMSCount(), 0)

        # Test Create
        sms = SMS()
        self.setRandomSMSValues(sms)
        sms.save()

        sleep(1)
        self.assertEqual(self.getSMSLogCount(), 1)
        self.assertEqual(self.getSMSCount(), 1)

        smslog = FRISMSLog.get(sms.couch_id)
        self.checkFieldValues(smslog, sms, SMS._migration_get_fields())
        self.assertTrue(FRISMSLog.get_db().get_rev(smslog._id).startswith('2-'))

        # Test Update
        self.setRandomSMSValues(sms)
        sms.save()

        sleep(1)
        self.assertEqual(self.getSMSLogCount(), 1)
        self.assertEqual(self.getSMSCount(), 1)
        smslog = FRISMSLog.get(sms.couch_id)
        self.checkFieldValues(smslog, sms, SMS._migration_get_fields())
        self.assertTrue(FRISMSLog.get_db().get_rev(smslog._id).startswith('3-'))


class CallMigrationTestCase(BaseMigrationTestCase):
    def getCallLogCount(self):
        result = CallLog.view(
            'sms/by_domain',
            startkey=[self.domain, 'CallLog'],
            endkey=[self.domain, 'CallLog', {}],
            include_docs=False,
            reduce=True,
        ).all()
        if result:
            return result[0]['value']
        return 0

    def getCallCount(self):
        return Call.objects.filter(domain=self.domain).count()

    def setRandomCallLogValues(self, calllog):
        calllog.form_unique_id = self.randomString()
        calllog.answered = self.randomBoolean()
        calllog.duration = self.randomInteger()
        calllog.gateway_session_id = self.randomString()
        calllog.xforms_session_id = self.randomString()
        calllog.error_message = self.randomString()
        calllog.submit_partial_form = self.randomBoolean()
        calllog.include_case_side_effects = self.randomBoolean()
        calllog.max_question_retries = self.randomInteger()
        calllog.current_question_retry_count = self.randomInteger()
        calllog.use_precached_first_response = self.randomBoolean()
        calllog.first_response = self.randomString()
        calllog.case_id = self.randomString()
        calllog.case_for_case_submission = self.randomBoolean()
        calllog.messaging_subevent_id = self.randomMessagingSubEventId()
        calllog.couch_recipient_doc_type = self.randomString()
        calllog.couch_recipient = self.randomString()
        calllog.phone_number = self.randomString()
        calllog.direction = self.randomDirection()
        calllog.date = self.randomDateTime()
        calllog.domain = self.domain
        calllog.backend_api = self.randomString()
        calllog.backend_id = self.randomString()
        calllog.billed = self.randomBoolean()
        calllog.workflow = self.randomString()
        calllog.xforms_session_couch_id = self.randomString()
        calllog.reminder_id = self.randomString()
        calllog.error = self.randomBoolean()
        calllog.system_error_message = self.randomString()
        calllog.system_phone_number = self.randomString()
        calllog.location_id = self.randomString()

    def setRandomCallValues(self, call):
        call.domain = self.domain
        call.date = self.randomDateTime()
        call.couch_recipient_doc_type = self.randomString()
        call.couch_recipient = self.randomString()
        call.phone_number = self.randomString()
        call.direction = self.randomDirection()
        call.error = self.randomBoolean()
        call.system_error_message = self.randomString()
        call.system_phone_number = self.randomString()
        call.backend_api = self.randomString()
        call.backend_id = self.randomString()
        call.billed = self.randomBoolean()
        call.workflow = self.randomString()
        call.xforms_session_couch_id = self.randomString()
        call.reminder_id = self.randomString()
        call.location_id = self.randomString()
        call.messaging_subevent_id = self.randomMessagingSubEventId()
        call.answered = self.randomBoolean()
        call.duration = self.randomInteger()
        call.gateway_session_id = self.randomString()
        call.submit_partial_form = self.randomBoolean()
        call.include_case_side_effects = self.randomBoolean()
        call.max_question_retries = self.randomInteger()
        call.current_question_retry_count = self.randomInteger()
        call.xforms_session_id = self.randomString()
        call.error_message = self.randomString()
        call.use_precached_first_response
        call.first_response = self.randomString()
        call.case_id = self.randomString()
        call.case_for_case_submission = self.randomBoolean()
        call.form_unique_id = self.randomString()

    def testCallLogSync(self):
        self.deleteAllLogs()
        self.assertEqual(self.getCallLogCount(), 0)
        self.assertEqual(self.getCallCount(), 0)

        # Test Create
        calllog = CallLog()
        self.setRandomCallLogValues(calllog)
        calllog.save()

        sleep(1)
        self.assertEqual(self.getCallLogCount(), 1)
        self.assertEqual(self.getCallCount(), 1)

        call = Call.objects.get(couch_id=calllog._id)
        self.checkFieldValues(calllog, call, call._migration_get_fields())
        self.assertTrue(CallLog.get_db().get_rev(calllog._id).startswith('1-'))

        # Test Update
        self.setRandomCallLogValues(calllog)
        calllog.save()

        sleep(1)
        self.assertEqual(self.getCallLogCount(), 1)
        self.assertEqual(self.getCallCount(), 1)
        call = Call.objects.get(couch_id=calllog._id)
        self.checkFieldValues(calllog, call, Call._migration_get_fields())
        self.assertTrue(CallLog.get_db().get_rev(calllog._id).startswith('2-'))

    def testCallSync(self):
        self.deleteAllLogs()
        self.assertEqual(self.getCallLogCount(), 0)
        self.assertEqual(self.getCallCount(), 0)

        # Test Create
        call = Call()
        self.setRandomCallValues(call)
        call.save()

        sleep(1)
        self.assertEqual(self.getCallLogCount(), 1)
        self.assertEqual(self.getCallCount(), 1)

        calllog = CallLog.get(call.couch_id)
        self.checkFieldValues(calllog, call, Call._migration_get_fields())
        self.assertTrue(CallLog.get_db().get_rev(calllog._id).startswith('2-'))

        # Test Update
        self.setRandomCallValues(call)
        call.save()

        sleep(1)
        self.assertEqual(self.getCallLogCount(), 1)
        self.assertEqual(self.getCallCount(), 1)
        callog = CallLog.get(call.couch_id)
        self.checkFieldValues(callog, call, Call._migration_get_fields())
        self.assertTrue(CallLog.get_db().get_rev(callog._id).startswith('3-'))
