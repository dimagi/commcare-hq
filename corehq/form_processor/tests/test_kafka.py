import uuid
from django.test import TestCase, override_settings
from corehq.apps.change_feed import topics
from corehq.apps.change_feed.consumer.feed import change_meta_from_kafka_message
from corehq.form_processor.interfaces.dbaccessors import FormAccessors
from corehq.form_processor.tests import FormProcessorTestUtils
from corehq.form_processor.tests.utils import post_xform
from corehq.form_processor.utils import get_simple_form_xml
from corehq.util.test_utils import OverridableSettingsTestMixin, create_and_save_a_case, create_and_save_a_form
from testapps.test_pillowtop.utils import get_test_kafka_consumer


@override_settings(TESTS_SHOULD_USE_SQL_BACKEND=True)
class KafkaPublishingTest(OverridableSettingsTestMixin, TestCase):

    domain = 'kafka-publishing-test'

    def setUp(self):
        FormProcessorTestUtils.delete_all_sql_forms()
        FormProcessorTestUtils.delete_all_sql_cases()
        self.form_accessors = FormAccessors(domain=self.domain)

    def test_form_is_published(self):
        kafka_consumer = get_test_kafka_consumer(topics.FORM_SQL)
        form = create_and_save_a_form(self.domain)
        message = kafka_consumer.next()
        change_meta = change_meta_from_kafka_message(message.value)
        self.assertEqual(form.form_id, change_meta.document_id)
        self.assertEqual(self.domain, change_meta.domain)

    def test_case_is_published(self):
        kafka_consumer = get_test_kafka_consumer(topics.CASE_SQL)
        case = create_and_save_a_case(self.domain, case_id=uuid.uuid4().hex, case_name='test case')
        change_meta = change_meta_from_kafka_message(kafka_consumer.next().value)
        self.assertEqual(case.case_id, change_meta.document_id)
        self.assertEqual(self.domain, change_meta.domain)
