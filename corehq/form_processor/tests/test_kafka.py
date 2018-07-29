from __future__ import absolute_import
from __future__ import unicode_literals
import uuid
from django.test import TestCase
from corehq.apps.change_feed import topics
from corehq.apps.change_feed.consumer.feed import KafkaChangeFeed
from corehq.apps.commtrack.helpers import make_product
from corehq.apps.commtrack.tests.util import get_single_balance_block
from corehq.apps.hqcase.utils import submit_case_blocks
from corehq.apps.receiverwrapper.util import submit_form_locally
from corehq.form_processor.interfaces.dbaccessors import FormAccessors, CaseAccessors
from corehq.form_processor.tests.utils import FormProcessorTestUtils, use_sql_backend
from corehq.form_processor.utils import get_simple_form_xml, should_use_sql_backend
from corehq.util.test_utils import create_and_save_a_case, create_and_save_a_form
from pillowtop.pillow.interface import ConstructedPillow
from pillowtop.processors.sample import TestProcessor
from testapps.test_pillowtop.utils import process_pillow_changes


@use_sql_backend
class KafkaPublishingSQLTest(TestCase):

    domain = 'sql-kafka-publishing-test'

    def setUp(self):
        super(KafkaPublishingSQLTest, self).setUp()
        FormProcessorTestUtils.delete_all_cases_forms_ledgers()
        self.form_accessors = FormAccessors(domain=self.domain)
        self.processor = TestProcessor()
        self.case_pillow = ConstructedPillow(
            name='test-kafka-case-feed',
            checkpoint=None,
            change_feed=KafkaChangeFeed(topics=[topics.CASE, topics.CASE_SQL], group_id='test-kafka-case-feed'),
            processor=self.processor
        )
        self.ledger_pillow = ConstructedPillow(
            name='test-kafka-ledger-feed',
            checkpoint=None,
            change_feed=KafkaChangeFeed(topics=[topics.LEDGER], group_id='test-kafka-ledger-feed'),
            processor=self.processor
        )

    def test_duplicate_case_published(self):
        # this test only runs on sql because it's handling a sql-specific edge case where duplicate
        # form submissions should cause cases to be resubmitted.
        # see: http://manage.dimagi.com/default.asp?228463 for context
        case_id = uuid.uuid4().hex
        form_xml = get_simple_form_xml(uuid.uuid4().hex, case_id)
        submit_form_locally(form_xml, domain=self.domain)
        self.assertEqual(1, len(CaseAccessors(self.domain).get_case_ids_in_domain()))

        with process_pillow_changes(self.case_pillow):
            with process_pillow_changes('DefaultChangeFeedPillow'):
                dupe_form = submit_form_locally(form_xml, domain=self.domain).xform
                self.assertTrue(dupe_form.is_duplicate)

        # check the case was republished
        self.assertEqual(1, len(self.processor.changes_seen))
        case_meta = self.processor.changes_seen[0].metadata
        self.assertEqual(case_id, case_meta.document_id)
        self.assertEqual(self.domain, case_meta.domain)

    def test_duplicate_ledger_published(self):
        # this test also only runs on the sql backend for reasons described in test_duplicate_case_published
        # setup products and case
        product_a = make_product(self.domain, 'A Product', 'prodcode_a')
        product_b = make_product(self.domain, 'B Product', 'prodcode_b')
        case_id = uuid.uuid4().hex
        form_xml = get_simple_form_xml(uuid.uuid4().hex, case_id)
        submit_form_locally(form_xml, domain=self.domain)

        # submit ledger data
        balances = (
            (product_a._id, 100),
            (product_b._id, 50),
        )
        ledger_blocks = [
            get_single_balance_block(case_id, prod_id, balance)
            for prod_id, balance in balances
        ]
        form = submit_case_blocks(ledger_blocks, self.domain)[0]

        # submit duplicate
        with process_pillow_changes(self.ledger_pillow):
            with process_pillow_changes('DefaultChangeFeedPillow'):
                dupe_form = submit_form_locally(form.get_xml(), domain=self.domain).xform
                self.assertTrue(dupe_form.is_duplicate)

        # confirm republished
        ledger_meta_a = self.processor.changes_seen[0].metadata
        ledger_meta_b = self.processor.changes_seen[1].metadata
        format_id = lambda product_id: '{}/{}/{}'.format(case_id, 'stock', product_id)
        expected_ids = {format_id(product_a._id), format_id(product_b._id)}
        for meta in [ledger_meta_a, ledger_meta_b]:
            self.assertTrue(meta.document_id in expected_ids)
            expected_ids.remove(meta.document_id)
            self.assertEqual(self.domain, meta.domain)

        # cleanup
        product_a.delete()
        product_b.delete()


class KafkaPublishingTest(TestCase):

    domain = 'kafka-publishing-test'

    def setUp(self):
        super(KafkaPublishingTest, self).setUp()
        FormProcessorTestUtils.delete_all_cases_forms_ledgers()
        self.form_accessors = FormAccessors(domain=self.domain)
        self.processor = TestProcessor()
        self.form_pillow = ConstructedPillow(
            name='test-kafka-form-feed',
            checkpoint=None,
            change_feed=KafkaChangeFeed(topics=[topics.FORM, topics.FORM_SQL], group_id='test-kafka-form-feed'),
            processor=self.processor
        )
        self.case_pillow = ConstructedPillow(
            name='test-kafka-case-feed',
            checkpoint=None,
            change_feed=KafkaChangeFeed(topics=[topics.CASE, topics.CASE_SQL], group_id='test-kafka-case-feed'),
            processor=self.processor
        )
        self.ledger_pillow = ConstructedPillow(
            name='test-kafka-ledger-feed',
            checkpoint=None,
            change_feed=KafkaChangeFeed(topics=[topics.LEDGER], group_id='test-kafka-ledger-feed'),
            processor=self.processor
        )

    def tearDown(self):
        FormProcessorTestUtils.delete_all_cases_forms_ledgers()

    def test_form_is_published(self):
        with process_pillow_changes(self.form_pillow):
            with process_pillow_changes('DefaultChangeFeedPillow'):
                form = create_and_save_a_form(self.domain)

        self.assertEqual(1, len(self.processor.changes_seen))
        change_meta = self.processor.changes_seen[0].metadata
        self.assertEqual(form.form_id, change_meta.document_id)
        self.assertEqual(self.domain, change_meta.domain)

    def test_duplicate_form_published(self):
        form_id = uuid.uuid4().hex
        form_xml = get_simple_form_xml(form_id)
        orig_form = submit_form_locally(form_xml, domain=self.domain).xform
        self.assertEqual(form_id, orig_form.form_id)
        self.assertEqual(1, len(self.form_accessors.get_all_form_ids_in_domain()))

        with process_pillow_changes(self.form_pillow):
            with process_pillow_changes('DefaultChangeFeedPillow'):
                # post an exact duplicate
                dupe_form = submit_form_locally(form_xml, domain=self.domain).xform
                self.assertTrue(dupe_form.is_duplicate)
                self.assertNotEqual(form_id, dupe_form.form_id)
                if should_use_sql_backend(self.domain):
                    self.assertEqual(form_id, dupe_form.orig_id)

        # make sure changes made it to kafka
        dupe_form_meta = self.processor.changes_seen[0].metadata
        self.assertEqual(dupe_form.form_id, dupe_form_meta.document_id)
        self.assertEqual(dupe_form.domain, dupe_form.domain)
        if should_use_sql_backend(self.domain):
            # sql domains also republish the original form to ensure that if the server crashed
            # in the processing of the form the first time that it is still sent to kafka
            orig_form_meta = self.processor.changes_seen[1].metadata
            self.assertEqual(orig_form.form_id, orig_form_meta.document_id)
            self.assertEqual(self.domain, orig_form_meta.domain)
            self.assertEqual(dupe_form.domain, dupe_form.domain)

    def test_form_soft_deletions(self):
        form = create_and_save_a_form(self.domain)
        with process_pillow_changes(self.form_pillow):
            with process_pillow_changes('DefaultChangeFeedPillow'):
                form.soft_delete()

        self.assertEqual(1, len(self.processor.changes_seen))
        change_meta = self.processor.changes_seen[0].metadata
        self.assertEqual(form.form_id, change_meta.document_id)
        self.assertTrue(change_meta.is_deletion)

    def test_case_is_published(self):
        with process_pillow_changes(self.case_pillow):
            with process_pillow_changes('DefaultChangeFeedPillow'):
                case = create_and_save_a_case(self.domain, case_id=uuid.uuid4().hex, case_name='test case')

        self.assertEqual(1, len(self.processor.changes_seen))
        change_meta = self.processor.changes_seen[0].metadata
        self.assertEqual(case.case_id, change_meta.document_id)
        self.assertEqual(self.domain, change_meta.domain)

    def test_case_deletions(self):
        case = create_and_save_a_case(self.domain, case_id=uuid.uuid4().hex, case_name='test case')
        with process_pillow_changes(self.case_pillow):
            with process_pillow_changes('DefaultChangeFeedPillow'):
                case.soft_delete()

        self.assertEqual(1, len(self.processor.changes_seen))
        change_meta = self.processor.changes_seen[0].metadata
        self.assertEqual(case.case_id, change_meta.document_id)
        self.assertTrue(change_meta.is_deletion)


@use_sql_backend
class KafkaPublishingTestSQL(KafkaPublishingTest):
    pass
