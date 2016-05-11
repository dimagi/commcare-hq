import uuid
from django.test import TestCase, override_settings

from casexml.apps.case.mock import CaseFactory
from corehq.apps.change_feed import topics
from corehq.apps.change_feed.consumer.feed import change_meta_from_kafka_message
from corehq.apps.es import CaseES
from corehq.elastic import get_es_new
from corehq.form_processor.parsers.ledgers.helpers import UniqueLedgerReference
from corehq.form_processor.tests.utils import FormProcessorTestUtils
from corehq.pillows.case import CasePillow, get_sql_case_to_elasticsearch_pillow
from corehq.pillows.ledger import get_ledger_to_elasticsearch_pillow
from corehq.pillows.mappings.case_search_mapping import CASE_SEARCH_INDEX_INFO
from corehq.pillows.mappings.ledger_mapping import LEDGER_INDEX_INFO
from corehq.util.elastic import delete_es_index, ensure_index_deleted
from corehq.util.test_utils import trap_extra_setup, create_and_save_a_case
from elasticsearch.exceptions import ConnectionError

from pillowtop.es_utils import initialize_index_and_mapping
from testapps.test_pillowtop.utils import get_test_kafka_consumer


@override_settings(TESTS_SHOULD_USE_SQL_BACKEND=True)
class LedgerPillowTest(TestCase):

    domain = 'ledger-pillowtest-domain'

    def setUp(self):
        FormProcessorTestUtils.delete_all_cases(self.domain)
        FormProcessorTestUtils.delete_all_ledgers(self.domain)
        with trap_extra_setup(ConnectionError):
            self.pillow = get_ledger_to_elasticsearch_pillow()
        self.elasticsearch = get_es_new()
        ensure_index_deleted(LEDGER_INDEX_INFO.index)
        initialize_index_and_mapping(get_es_new(), LEDGER_INDEX_INFO)

        self.factory = CaseFactory(domain=self.domain)
        self.case = self.factory.create_case()

    def tearDown(self):
        ensure_index_deleted(LEDGER_INDEX_INFO.index)

    def test_ledger_pillow_sql(self):
        consumer = get_test_kafka_consumer(topics.LEDGER)
        # have to get the seq id before the change is processed
        kafka_seq = consumer.offsets()['fetch'][(topics.LEDGER, 0)]

        product_id = 'prod_1'
        from corehq.apps.commtrack.tests import get_single_balance_block
        from corehq.apps.hqcase.utils import submit_case_blocks
        submit_case_blocks([
            get_single_balance_block(self.case.case_id, product_id, 100)],
            self.domain
        )

        ref = UniqueLedgerReference(self.case.case_id, 'stock', product_id)
        # confirm change made it to kafka
        message = consumer.next()
        change_meta = change_meta_from_kafka_message(message.value)
        self.assertEqual(ref.as_id(), change_meta.document_id)
        self.assertEqual(self.domain, change_meta.domain)

        # send to elasticsearch
        self.pillow.process_changes(since=kafka_seq, forever=False)
        self.elasticsearch.indices.refresh(LEDGER_INDEX_INFO)

        # confirm change made it to elasticserach
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
        self.assertEqual(1, results.total)
        ledger_doc = results.hits[0]
        self.assertEqual(self.domain, ledger_doc['domain'])
        self.assertEqual(ref.case_id, ledger_doc['case_id'])
        self.assertEqual(ref.section_id, ledger_doc['section_id'])
        self.assertEqual(ref.entry_id, ledger_doc['entry_id'])
