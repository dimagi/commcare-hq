import uuid

from django.test import TestCase

from corehq.apps.app_manager.models import Application
from corehq.apps.app_manager.tests.app_factory import AppFactory
from corehq.apps.change_feed import topics
from corehq.apps.change_feed.consumer.feed import (
    change_meta_from_kafka_message,
)
from corehq.apps.change_feed.tests.utils import get_test_kafka_consumer
from corehq.apps.change_feed.topics import get_topic_offset
from corehq.apps.es.forms import form_adapter
from corehq.apps.es.tests.utils import es_test
from corehq.apps.es.users import user_adapter
from corehq.apps.receiverwrapper.util import submit_form_locally
from corehq.form_processor.tests.utils import FormProcessorTestUtils
from corehq.form_processor.utils import TestFormMetadata, get_simple_form_xml
from corehq.pillows.xform import get_xform_pillow


@es_test(requires=[form_adapter, user_adapter], setup_class=True)
class FormPillowTest(TestCase):
    domain = 'test-form-pillow-domain'

    def setUp(self):
        super(FormPillowTest, self).setUp()
        FormProcessorTestUtils.delete_all_xforms()
        self.pillow = get_xform_pillow(skip_ucr=True)
        factory = AppFactory(domain=self.domain)
        self.app = factory.app
        self.app.save()

    def tearDown(self):
        self.app.delete()
        super(FormPillowTest, self).tearDown()

    def test_form_pillow_sql(self):
        consumer = get_test_kafka_consumer(topics.FORM_SQL)
        kafka_seq = self._get_kafka_seq()

        form = self._make_form()

        # confirm change made it to kafka
        message = next(consumer)
        change_meta = change_meta_from_kafka_message(message.value)
        self.assertEqual(form.form_id, change_meta.document_id)
        self.assertEqual(self.domain, change_meta.domain)
        self.assertFalse(self.app.has_submissions)

        self.pillow.process_changes(since=kafka_seq, forever=False)
        self.assertTrue(Application.get(self.app._id).has_submissions)

    def test_form_pillow_non_existant_build_id(self):
        consumer = get_test_kafka_consumer(topics.FORM_SQL)
        kafka_seq = self._get_kafka_seq()

        form = self._make_form(build_id='not-here')

        # confirm change made it to kafka
        message = next(consumer)
        change_meta = change_meta_from_kafka_message(message.value)
        self.assertEqual(form.form_id, change_meta.document_id)
        self.assertEqual(self.domain, change_meta.domain)
        self.assertFalse(self.app.has_submissions)

        self.pillow.process_changes(since=kafka_seq, forever=False)
        self.assertFalse(Application.get(self.app._id).has_submissions)

    def test_form_pillow_mismatch_domains(self):
        consumer = get_test_kafka_consumer(topics.FORM_SQL)
        kafka_seq = self._get_kafka_seq()
        self.app.domain = 'not-this-domain'
        self.app.save()

        form = self._make_form()

        # confirm change made it to kafka
        message = next(consumer)
        change_meta = change_meta_from_kafka_message(message.value)
        self.assertEqual(form.form_id, change_meta.document_id)
        self.assertEqual(self.domain, change_meta.domain)
        self.assertFalse(self.app.has_submissions)

        self.pillow.process_changes(since=kafka_seq, forever=False)
        self.assertFalse(Application.get(self.app._id).has_submissions)

    def test_two_forms_with_same_app(self):
        """Ensures two forms submitted to the same app does not error"""
        kafka_seq = self._get_kafka_seq()

        self._make_form()

        # confirm change made it to kafka
        self.assertFalse(self.app.has_submissions)

        self.pillow.process_changes(since=kafka_seq, forever=False)
        newly_saved_app = Application.get(self.app._id)
        self.assertTrue(newly_saved_app.has_submissions)
        # Ensure that the app has been saved
        self.assertNotEqual(self.app._rev, newly_saved_app._rev)

        self._make_form()
        self.pillow.process_changes(since=kafka_seq, forever=False)
        self.assertTrue(Application.get(self.app._id).has_submissions)
        # Ensure that the app has not been saved twice
        self.assertEqual(Application.get(self.app._id)._rev, newly_saved_app._rev)

    def _make_form(self, build_id=None):
        metadata = TestFormMetadata(domain=self.domain)
        form_xml = get_simple_form_xml(uuid.uuid4().hex, metadata=metadata)
        result = submit_form_locally(
            form_xml,
            self.domain,
            build_id=build_id or self.app._id
        )
        return result.xform

    def _get_kafka_seq(self):
        return get_topic_offset(topics.FORM_SQL)
