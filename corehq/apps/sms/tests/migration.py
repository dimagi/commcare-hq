from corehq.apps.sms.models import (SMSLog, SMS, INCOMING, OUTGOING,
    MessagingEvent, MessagingSubEvent)
from custom.fri.models import FRISMSLog, PROFILES
from datetime import datetime, timedelta
from django.test import TestCase
import random
import string
from time import sleep


class SQLMigrationTestCase(TestCase):
    def setUp(self):
        self.domain = 'test-sms-sql-migration'

    def tearDown(self):
        for smslog in SMSLog.view(
            'sms/by_domain',
            startkey=[self.domain, 'SMSLog'],
            endkey=[self.domain, 'SMSLog', {}],
            include_docs=True,
            reduce=False,
        ).all():
            smslog.delete()

        SMS.objects.filter(domain=self.domain).delete()

    def randomDirection(self):
        [INCOMING, OUTGOING][random.randint(0, 1)]

    def randomBoolean(self):
        [True, False][random.randint(0, 1)]

    def randomString(self, length=10):
        ''.join([random.choice(string.lowercase) for i in range(length)])

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

    def checkFieldValues(self, object1, object2, fields):
        for field_name in fields:
            self.assertEqual(getattr(object1, field_name), getattr(object2, field_name))

    def testSMSLogSync(self):
        prev_couch_count = self.getSMSLogCount()
        prev_sql_count = self.getSMSCount()

        # Test Create
        smslog = SMSLog()
        self.setRandomSMSLogValues(smslog)
        smslog.save()

        sleep(1)
        self.assertEqual(self.getSMSLogCount(), prev_couch_count + 1)
        self.assertEqual(self.getSMSCount(), prev_sql_count + 1)

        sms = SMS.objects.get(couch_id=smslog._id)
        self.checkFieldValues(smslog, sms, SMSLog._migration_get_fields())
        self.assertTrue(SMSLog.get_db().get_rev(smslog._id).startswith('1-'))

        # Test Update
        self.setRandomSMSLogValues(smslog)
        smslog.save()

        sleep(1)
        self.assertEqual(self.getSMSLogCount(), prev_couch_count + 1)
        self.assertEqual(self.getSMSCount(), prev_sql_count + 1)
        sms = SMS.objects.get(couch_id=smslog._id)
        self.checkFieldValues(smslog, sms, SMSLog._migration_get_fields())
        self.assertTrue(SMSLog.get_db().get_rev(smslog._id).startswith('2-'))

    def testFRISMSLogSync(self):
        prev_couch_count = self.getSMSLogCount()
        prev_sql_count = self.getSMSCount()

        # Test Create
        smslog = SMSLog()
        self.setRandomSMSLogValues(smslog)
        smslog.save()

        sleep(1)
        smslog = FRISMSLog.get(smslog._id)
        self.setRandomFRISMSLogValues(smslog)
        smslog.save()

        sleep(1)
        self.assertEqual(self.getSMSLogCount(), prev_couch_count + 1)
        self.assertEqual(self.getSMSCount(), prev_sql_count + 1)

        sms = SMS.objects.get(couch_id=smslog._id)
        self.checkFieldValues(smslog, sms, FRISMSLog._migration_get_fields())
        self.assertTrue(FRISMSLog.get_db().get_rev(smslog._id).startswith('2-'))

        # Test Update
        self.setRandomSMSLogValues(smslog)
        self.setRandomFRISMSLogValues(smslog)
        smslog.save()

        sleep(1)
        self.assertEqual(self.getSMSLogCount(), prev_couch_count + 1)
        self.assertEqual(self.getSMSCount(), prev_sql_count + 1)
        sms = SMS.objects.get(couch_id=smslog._id)
        self.checkFieldValues(smslog, sms, FRISMSLog._migration_get_fields())
        self.assertTrue(SMSLog.get_db().get_rev(smslog._id).startswith('3-'))

    def testSMSSync(self):
        prev_couch_count = self.getSMSLogCount()
        prev_sql_count = self.getSMSCount()

        # Test Create
        sms = SMS()
        self.setRandomSMSValues(sms)
        sms.save()

        sleep(1)
        self.assertEqual(self.getSMSLogCount(), prev_couch_count + 1)
        self.assertEqual(self.getSMSCount(), prev_sql_count + 1)

        smslog = FRISMSLog.get(sms.couch_id)
        self.checkFieldValues(smslog, sms, SMS._migration_get_fields())
        self.assertTrue(FRISMSLog.get_db().get_rev(smslog._id).startswith('2-'))

        # Test Update
        self.setRandomSMSValues(sms)
        sms.save()

        sleep(1)
        self.assertEqual(self.getSMSLogCount(), prev_couch_count + 1)
        self.assertEqual(self.getSMSCount(), prev_sql_count + 1)
        smslog = FRISMSLog.get(sms.couch_id)
        self.checkFieldValues(smslog, sms, SMS._migration_get_fields())
        self.assertTrue(FRISMSLog.get_db().get_rev(smslog._id).startswith('3-'))
