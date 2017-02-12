from django.conf import settings
from django.core.management import call_command
from django.test import TestCase
from elasticsearch.exceptions import ConnectionError

from casexml.apps.case.mock import CaseFactory
from corehq.apps.change_feed import topics
from corehq.apps.change_feed.consumer.feed import change_meta_from_kafka_message
from corehq.apps.change_feed.tests.utils import get_test_kafka_consumer
from corehq.apps.change_feed.topics import get_topic_offset
from corehq.elastic import get_es_new
from corehq.form_processor.parsers.ledgers.helpers import UniqueLedgerReference
from corehq.form_processor.tests.utils import FormProcessorTestUtils, conditionally_run_with_all_backends
from corehq.form_processor.utils.general import should_use_sql_backend
from corehq.pillows.ledger import get_ledger_to_elasticsearch_pillow
from corehq.pillows.mappings.ledger_mapping import LEDGER_INDEX_INFO
from corehq.util.elastic import ensure_index_deleted
from corehq.util.test_utils import trap_extra_setup
from pillowtop.es_utils import initialize_index_and_mapping


class LedgerPillowTest(TestCase):

    domain = 'ledger-pillowtest-domain'

    @classmethod
    def setUpClass(cls):
        super(LedgerPillowTest, cls).setUpClass()
        from corehq.apps.commtrack.helpers import make_product
        product = make_product(cls.domain, 'Product A', 'prod_a')
        cls.product_id = product._id

    def setUp(self):
        super(LedgerPillowTest, self).setUp()
        FormProcessorTestUtils.delete_all_ledgers(self.domain)
        FormProcessorTestUtils.delete_all_cases(self.domain)
        with trap_extra_setup(ConnectionError):
            self.pillow = get_ledger_to_elasticsearch_pillow()
        self.elasticsearch = get_es_new()
        ensure_index_deleted(LEDGER_INDEX_INFO.index)
        initialize_index_and_mapping(get_es_new(), LEDGER_INDEX_INFO)

    def tearDown(self):
        ensure_index_deleted(LEDGER_INDEX_INFO.index)
        FormProcessorTestUtils.delete_all_ledgers(self.domain)
        FormProcessorTestUtils.delete_all_cases(self.domain)
        super(LedgerPillowTest, self).tearDown()

    @conditionally_run_with_all_backends
    def test_ledger_pillow(self):
        factory = CaseFactory(domain=self.domain)
        case = factory.create_case()

        consumer = get_test_kafka_consumer(topics.LEDGER)
        # have to get the seq id before the change is processed
        kafka_seq = get_topic_offset(topics.LEDGER)

        from corehq.apps.commtrack.tests.util import get_single_balance_block
        from corehq.apps.hqcase.utils import submit_case_blocks
        submit_case_blocks([
            get_single_balance_block(case.case_id, self.product_id, 100)],
            self.domain
        )

        ref = UniqueLedgerReference(case.case_id, 'stock', self.product_id)
        # confirm change made it to kafka
        message = consumer.next()
        change_meta = change_meta_from_kafka_message(message.value)
        if should_use_sql_backend(self.domain):
            self.assertEqual(ref.as_id(), change_meta.document_id)
        else:
            from corehq.apps.commtrack.models import StockState
            state = StockState.objects.all()
            self.assertEqual(1, len(state))
            self.assertEqual(state[0].pk, change_meta.document_id)  #
        self.assertEqual(self.domain, change_meta.domain)

        # send to elasticsearch
        self.pillow.process_changes(since=kafka_seq, forever=False)
        self.elasticsearch.indices.refresh(LEDGER_INDEX_INFO.index)

        # confirm change made it to elasticserach
        self._assert_ledger_in_es(ref)

    @conditionally_run_with_all_backends
    def test_ledger_reindexer(self):
        factory = CaseFactory(domain=self.domain)
        case = factory.create_case()

        from corehq.apps.commtrack.tests.util import get_single_balance_block
        from corehq.apps.hqcase.utils import submit_case_blocks
        submit_case_blocks([
            get_single_balance_block(case.case_id, self.product_id, 100)],
            self.domain
        )

        ref = UniqueLedgerReference(case.case_id, 'stock', self.product_id)

        index_id = 'ledger-v2' if settings.TESTS_SHOULD_USE_SQL_BACKEND else 'ledger-v1'
        call_command('ptop_reindexer_v2', index_id, cleanup=True, noinput=True, reset=True)

        self._assert_ledger_in_es(ref)

    def _assert_ledger_in_es(self, ref):
        results = self.elasticsearch.search(
            LEDGER_INDEX_INFO.index,
            LEDGER_INDEX_INFO.type, body={
                "query": {
                    "bool": {
                        "must": [{
                            "match_all": {}
                        }]
                    }
                }
            }
        )
        self.assertEqual(1, results['hits']['total'])
        ledger_doc = results['hits']['hits'][0]['_source']
        self.assertEqual(self.domain, ledger_doc['domain'])
        self.assertEqual(ref.case_id, ledger_doc['case_id'])
        self.assertEqual(ref.section_id, ledger_doc['section_id'])
        self.assertEqual(ref.entry_id, ledger_doc['entry_id'])
