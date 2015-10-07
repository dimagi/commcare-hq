import uuid
from django.test import SimpleTestCase
from corehq.pillows.case import CasePillow
from corehq.pillows.mappings.case_mapping import CASE_MAPPING
from pillowtop.feed.interface import Change
from ..decorators import require_explicit_elasticsearch_testing


class CasePillowTest(SimpleTestCase):

    @require_explicit_elasticsearch_testing
    def setUp(self):
        pillow = CasePillow(create_index=False, online=False)
        self.index = pillow.es_index
        self.es = pillow.get_es_new()
        if self.es.indices.exists(self.index):
            self.es.indices.delete(self.index)
        self.assertFalse(self.es.indices.exists(self.index))

    def test_create_index_on_pillow_creation(self):
        pillow = CasePillow()
        self.assertEqual(self.index, pillow.es_index)
        self.assertTrue(self.es.indices.exists(self.index))
        self.es.indices.delete(pillow.es_index)
        self.assertFalse(self.es.indices.exists(self.index))

    def test_mapping_initialization_on_pillow_creation(self):
        pillow = CasePillow()
        mapping = pillow.get_index_mapping()['case']
        # this is totally arbitrary, but something obscure enough that we can assume it worked
        # we can't compare the whole dicts because ES adds a bunch of stuff to them
        self.assertEqual(
            CASE_MAPPING['properties']['actions']['properties']['date']['format'],
            mapping['properties']['actions']['properties']['date']['format']
        )

    def test_refresh_index(self):
        pillow = CasePillow()
        doc_id = uuid.uuid4().hex
        doc = {'_id': doc_id, 'doc_type': 'CommCareCase', 'type': 'mother'}
        self.assertEqual(0, _get_doc_count(self.es, self.index))
        self.es.create(self.index, 'case', doc, id=doc_id)
        self.assertEqual(0, _get_doc_count(self.es, self.index, refresh_first=False))
        pillow.refresh_index()
        self.assertEqual(1, _get_doc_count(self.es, self.index, refresh_first=False))

    def test_send_case_to_es(self):
        pillow = CasePillow()
        doc_id = uuid.uuid4().hex
        change = Change(
            id=doc_id,
            sequence_id=0,
            document={'_id': doc_id, 'doc_type': 'CommCareCase', 'type': 'mother'}
        )
        pillow.processor(change, False)
        self.assertEqual(1, _get_doc_count(self.es, self.index))
        doc = self.es.get_source(self.index, doc_id)
        self.assertEqual('CommCareCase', doc['doc_type'])
        self.assertEqual('mother', doc['type'])

    def test_send_case_bulk(self):
        # this structure determined based on seeing what bulk_reindex does
        def make_bulk_row(doc):
            return {
                'key': [None, None, False],
                'doc': doc,
                'id': doc['_id'],
                'value': None
            }

        doc_ids = [uuid.uuid4().hex for i in range(3)]
        docs = [{'_id': doc_id, 'doc_type': 'CommCareCase', 'type': 'mother'} for doc_id in doc_ids]
        rows = [make_bulk_row(doc) for doc in docs]
        pillow = CasePillow()
        pillow.process_bulk(rows)
        self.assertEqual(len(doc_ids), _get_doc_count(self.es, self.index))
        for doc in docs:
            es_doc = self.es.get_source(self.index, doc['_id'])
            for prop in doc.keys():
                self.assertEqual(doc[prop], es_doc[prop])


def _get_doc_count(es, index, refresh_first=True):
    if refresh_first:
        # we default to calling refresh since ES might have stale data
        es.indices.refresh(index)
    stats = es.indices.stats(index)
    return stats['indices'][index]['total']['docs']['count']
