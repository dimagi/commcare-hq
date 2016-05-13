from corehq.apps.change_feed import topics
from corehq.apps.change_feed.consumer.feed import change_meta_from_kafka_message
from corehq.apps.es.sms import SMSES
from corehq.apps.sms.models import MessagingEvent, MessagingSubEvent, SMS
from corehq.elastic import get_es_new
from corehq.pillows.mappings.sms_mapping import SMS_INDEX_INFO
from corehq.pillows.sms import get_sql_sms_pillow
from corehq.util.elastic import ensure_index_deleted
from datetime import datetime
from dimagi.utils.parsing import json_format_datetime
from django.test import TestCase
from mock import patch
from testapps.test_pillowtop.utils import get_test_kafka_consumer


@patch('corehq.apps.sms.change_publishers.do_publish')
class SqlSMSPillowTest(TestCase):
    dependent_apps = ['corehq.apps.sms', 'corehq.apps.smsforms']

    domain = 'sms-pillow-test-domain'

    def setUp(self):
        self.elasticsearch = get_es_new()
        ensure_index_deleted(SMS_INDEX_INFO.index)

    def tearDown(self):
        ensure_index_deleted(SMS_INDEX_INFO.index)
        SMS.objects.filter(domain=self.domain).delete()
        MessagingSubEvent.objects.filter(parent__domain=self.domain).delete()
        MessagingEvent.objects.filter(domain=self.domain).delete()

    def _create_sms(self):
        event = MessagingEvent.objects.create(
            domain=self.domain,
            date=datetime(2016, 1, 1, 12, 0),
            source=MessagingEvent.SOURCE_OTHER,
            source_id=None,
            content_type=MessagingEvent.CONTENT_SMS,
            form_unique_id=None,
            form_name=None,
            status=MessagingEvent.STATUS_COMPLETED,
            error_code=None,
            additional_error_text=None,
            recipient_type=None,
            recipient_id=None
        )
        subevent = MessagingSubEvent.objects.create(
            parent=event,
            date=datetime(2016, 1, 1, 12, 0),
            recipient_type=MessagingEvent.RECIPIENT_CASE,
            recipient_id=None,
            content_type=MessagingEvent.CONTENT_SMS,
            form_unique_id=None,
            form_name=None,
            xforms_session=None,
            case_id=None,
            status=MessagingEvent.STATUS_COMPLETED,
            error_code=None,
            additional_error_text=None
        )
        # Some of the values here don't apply for a simple outgoing SMS,
        # but the point of this is to just test the serialization and that
        # everything makes it to elasticsearch
        self.sms_dict = dict(
            domain=self.domain,
            date=datetime(2016, 1, 1, 12, 0),
            couch_recipient_doc_type='CommCareCase',
            couch_recipient='fake-case-id',
            phone_number='99912345678',
            direction='O',
            error=False,
            system_error_message='n/a',
            system_phone_number='00000',
            backend_api='TEST',
            backend_id='fake-backend-id',
            billed=False,
            workflow='default',
            xforms_session_couch_id='fake-session-couch-id',
            reminder_id='fake-reminder-id',
            location_id='fake-location-id',
            messaging_subevent_id=subevent.pk,
            text='test sms text',
            raw_text='raw text',
            datetime_to_process=datetime(2016, 1, 1, 11, 59),
            processed=True,
            num_processing_attempts=1,
            queued_timestamp=datetime(2016, 1, 1, 11, 58),
            processed_timestamp=datetime(2016, 1, 1, 12, 01),
            domain_scope=self.domain,
            ignore_opt_out=False,
            backend_message_id='fake-backend-message-id',
            chat_user_id='fake-user-id',
            invalid_survey_response=False,
            fri_message_bank_lookup_completed=True,
            fri_message_bank_message_id='bank-id',
            fri_id='12345',
            fri_risk_profile='X',
        )
        self.sms = SMS.objects.create(
            **self.sms_dict
        )

    def _to_json(self, sms_dict, sms):
        result = {'_id': sms.couch_id, 'id': sms.pk}
        for k, v in sms_dict.iteritems():
            value = json_format_datetime(v) if isinstance(v, datetime) else v
            result[k] = value

        return result

    def test_sql_sms_pillow(self, mock_do_publish):
        mock_do_publish.return_value = True
        consumer = get_test_kafka_consumer(topics.SMS)

        # get the seq id before the change is published
        kafka_seq = consumer.offsets()['fetch'][(topics.SMS, 0)]

        # create an sms
        self._create_sms()
        sms_json = self._to_json(self.sms_dict, self.sms)

        # test serialization
        self.assertEqual(self.sms.to_json(), sms_json)

        # publish the change and confirm it gets to kafka
        self.sms.publish_change()
        message = consumer.next()
        change_meta = change_meta_from_kafka_message(message.value)
        self.assertEqual(self.sms.couch_id, change_meta.document_id)
        self.assertEqual(self.domain, change_meta.domain)

        # send to elasticsearch
        sms_pillow = get_sql_sms_pillow('SqlSMSPillow')
        sms_pillow.process_changes(since=kafka_seq, forever=False)
        self.elasticsearch.indices.refresh(SMS_INDEX_INFO.index)

        # confirm change made it to elasticserach
        results = SMSES().run()
        self.assertEqual(1, results.total)
        sms_doc = results.hits[0]
        self.assertEqual(sms_doc, sms_json)
