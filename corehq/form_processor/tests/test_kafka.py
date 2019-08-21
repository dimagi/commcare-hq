from __future__ import absolute_import
from __future__ import unicode_literals

import uuid

from django.test import TestCase

from corehq.apps.change_feed import topics
from corehq.apps.change_feed.consumer.feed import KafkaChangeFeed
from corehq.form_processor.interfaces.dbaccessors import FormAccessors
from corehq.form_processor.tests.utils import FormProcessorTestUtils, use_sql_backend
from corehq.util.test_utils import create_and_save_a_case, create_and_save_a_form
from pillowtop.pillow.interface import ConstructedPillow
from pillowtop.processors.sample import TestProcessor
from testapps.test_pillowtop.utils import process_pillow_changes


class KafkaPublishingTest(TestCase):

    domain = 'kafka-publishing-test'

    def setUp(self):
        super(KafkaPublishingTest, self).setUp()
        FormProcessorTestUtils.delete_all_cases_forms_ledgers()
        self.processor.reset()

    @classmethod
    def setUpClass(cls):
        super(KafkaPublishingTest, cls).setUpClass()
        cls.form_accessors = FormAccessors(domain=cls.domain)
        cls.processor = TestProcessor()
        cls.form_pillow = ConstructedPillow(
            name='test-kafka-form-feed',
            checkpoint=None,
            change_feed=KafkaChangeFeed(topics=[topics.FORM, topics.FORM_SQL], client_id='test-kafka-form-feed'),
            processor=cls.processor
        )
        cls.case_pillow = ConstructedPillow(
            name='test-kafka-case-feed',
            checkpoint=None,
            change_feed=KafkaChangeFeed(topics=[topics.CASE, topics.CASE_SQL], client_id='test-kafka-case-feed'),
            processor=cls.processor
        )
        cls.process_form_changes = process_pillow_changes('DefaultChangeFeedPillow')
        cls.process_form_changes.add_pillow(cls.form_pillow)

        cls.process_case_changes = process_pillow_changes('DefaultChangeFeedPillow')
        cls.process_case_changes.add_pillow(cls.case_pillow)

    def tearDown(self):
        FormProcessorTestUtils.delete_all_cases_forms_ledgers()

    def test_form_is_published(self):
        with self.process_form_changes:
            form = create_and_save_a_form(self.domain)

        self.assertEqual(1, len(self.processor.changes_seen))
        change_meta = self.processor.changes_seen[0].metadata
        self.assertEqual(form.form_id, change_meta.document_id)
        self.assertEqual(self.domain, change_meta.domain)

    def test_form_soft_deletions(self):
        form = create_and_save_a_form(self.domain)
        with self.process_form_changes:
            form.soft_delete()

        self.assertEqual(1, len(self.processor.changes_seen))
        change_meta = self.processor.changes_seen[0].metadata
        self.assertEqual(form.form_id, change_meta.document_id)
        self.assertTrue(change_meta.is_deletion)

    def test_case_is_published(self):
        with self.process_case_changes:
            case = create_and_save_a_case(self.domain, case_id=uuid.uuid4().hex, case_name='test case')

        self.assertEqual(1, len(self.processor.changes_seen))
        change_meta = self.processor.changes_seen[0].metadata
        self.assertEqual(case.case_id, change_meta.document_id)
        self.assertEqual(self.domain, change_meta.domain)

    def test_case_deletions(self):
        case = create_and_save_a_case(self.domain, case_id=uuid.uuid4().hex, case_name='test case')
        with self.process_case_changes:
            case.soft_delete()

        self.assertEqual(1, len(self.processor.changes_seen))
        change_meta = self.processor.changes_seen[0].metadata
        self.assertEqual(case.case_id, change_meta.document_id)
        self.assertTrue(change_meta.is_deletion)


@use_sql_backend
class KafkaPublishingTestSQL(KafkaPublishingTest):
    pass
