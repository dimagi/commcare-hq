from datetime import datetime
from unittest.mock import patch

from django.test import TestCase

from dimagi.utils.parsing import json_format_datetime

from corehq.apps.change_feed import topics
from corehq.apps.change_feed.consumer.feed import (
    change_meta_from_kafka_message,
)
from corehq.apps.change_feed.tests.utils import get_test_kafka_consumer
from corehq.apps.change_feed.topics import get_topic_offset
from corehq.apps.es.client import manager
from corehq.apps.es.sms import SMSES, sms_adapter
from corehq.apps.es.tests.utils import es_test
from corehq.apps.sms.tests.data_generator import create_fake_sms
from corehq.pillows.sms import get_sql_sms_pillow


@patch('corehq.apps.sms.change_publishers.do_publish')
@es_test(requires=[sms_adapter])
class SqlSMSPillowTest(TestCase):

    domain = 'sms-pillow-test-domain'

    def _to_json(self, sms_dict, sms):
        result = {
            '_id': sms.couch_id,
            'id': sms.pk,
            'date_modified': json_format_datetime(sms.date_modified)
        }
        for k, v in sms_dict.items():
            if k != 'couch_id':
                value = json_format_datetime(v) if isinstance(v, datetime) else v
                result[k] = value

        return result

    def test_sql_sms_pillow(self, mock_do_publish):
        mock_do_publish.return_value = True
        consumer = get_test_kafka_consumer(topics.SMS)

        # get the seq id before the change is published
        kafka_seq = get_topic_offset(topics.SMS)

        # create an sms
        sms_and_dict = create_fake_sms(self.domain)
        self.sms = sms_and_dict.sms
        sms_json = self._to_json(sms_and_dict.sms_dict, self.sms)

        # test serialization
        self.assertEqual(self.sms.to_json(), sms_json)

        # publish the change and confirm it gets to kafka
        self.sms.publish_change()
        message = next(consumer)
        change_meta = change_meta_from_kafka_message(message.value)
        self.assertEqual(self.sms.couch_id, change_meta.document_id)
        self.assertEqual(self.domain, change_meta.domain)

        # send to elasticsearch
        sms_pillow = get_sql_sms_pillow('SqlSMSPillow')
        sms_pillow.process_changes(since=kafka_seq, forever=False)
        manager.index_refresh(sms_adapter.index_name)

        # confirm change made it to elasticserach
        results = SMSES().run()
        self.assertEqual(1, results.total)
        sms_doc = results.hits[0]
        sms_doc.pop('doc_id')
        self.assertEqual(sms_doc, sms_json)
