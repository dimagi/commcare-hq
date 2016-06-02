import uuid
from django.test import TestCase, override_settings
from corehq.apps.change_feed import topics
from corehq.apps.change_feed.consumer.feed import change_meta_from_kafka_message
from corehq.apps.change_feed.tests.utils import get_test_kafka_consumer
from corehq.apps.receiverwrapper import submit_form_locally
from corehq.form_processor.interfaces.dbaccessors import FormAccessors, CaseAccessors
from corehq.form_processor.tests import FormProcessorTestUtils
from corehq.form_processor.utils import get_simple_form_xml
from corehq.util.test_utils import OverridableSettingsTestMixin, create_and_save_a_case, create_and_save_a_form


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

    def test_duplicate_form_published(self):
        form_id = uuid.uuid4().hex
        form_xml = get_simple_form_xml(form_id)
        orig_form = submit_form_locally(form_xml, domain=self.domain)[1]
        self.assertEqual(form_id, orig_form.form_id)
        self.assertEqual(1, len(self.form_accessors.get_all_form_ids_in_domain()))

        form_consumer = get_test_kafka_consumer(topics.FORM_SQL)

        # post an exact duplicate
        dupe_form = submit_form_locally(form_xml, domain=self.domain)[1]
        self.assertTrue(dupe_form.is_duplicate)
        self.assertNotEqual(form_id, dupe_form.form_id)
        self.assertEqual(form_id, dupe_form.orig_id)

        # make sure changes made it to kafka
        # first the dupe
        dupe_form_meta = change_meta_from_kafka_message(form_consumer.next().value)
        self.assertEqual(dupe_form.form_id, dupe_form_meta.document_id)
        # then the original form
        orig_form_meta = change_meta_from_kafka_message(form_consumer.next().value)
        self.assertEqual(orig_form.form_id, orig_form_meta.document_id)
        self.assertEqual(self.domain, orig_form_meta.domain)

    def test_duplicate_case_published(self):
        case_id = uuid.uuid4().hex
        form_xml = get_simple_form_xml(uuid.uuid4().hex, case_id)
        submit_form_locally(form_xml, domain=self.domain)[1]
        self.assertEqual(1, len(CaseAccessors(self.domain).get_case_ids_in_domain()))

        case_consumer = get_test_kafka_consumer(topics.CASE_SQL)
        dupe_form = submit_form_locally(form_xml, domain=self.domain)[1]
        self.assertTrue(dupe_form.is_duplicate)

        # check the case was republished
        case_meta = change_meta_from_kafka_message(case_consumer.next().value)
        self.assertEqual(case_id, case_meta.document_id)
        self.assertEqual(self.domain, case_meta.domain)
