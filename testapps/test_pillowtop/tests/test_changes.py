import uuid
from django.test import TestCase
from mock import MagicMock
from couchforms.models import XFormInstance
from pillowtop.feed.couch import get_current_seq
from pillowtop.listener import BasicPillow


class ChangeFeedDbTest(TestCase):

    def setUp(self):
        super(ChangeFeedDbTest, self).setUp()
        self.couch_db = XFormInstance.get_db()
        self.update_seq = get_current_seq(self.couch_db)

    def test_basic_functionality(self):
        pillow = BasicPillow(couch_db=self.couch_db)
        self._apply_mocks_to_pillow(pillow)
        doc_id = uuid.uuid4().hex
        self.couch_db.save_doc({'_id': doc_id, 'property': 'property_value'})
        pillow.process_changes(since=self.update_seq, forever=False)

        change = self._extract_change_from_call_args(pillow.processor.call_args)
        # validate the structure of the change. some implicit asserts here
        self.assertEqual(doc_id, change['id'])
        doc = change['doc']
        self.assertEqual(doc_id, doc['_id'])
        self.assertEqual('property_value', doc['property'])

    def test_include_docs_false(self):
        pillow = BasicPillow(couch_db=self.couch_db)
        pillow.include_docs = False
        self._apply_mocks_to_pillow(pillow)
        doc_id = uuid.uuid4().hex
        self.couch_db.save_doc({'_id': doc_id, 'property': 'property_value'})
        pillow.process_changes(since=self.update_seq, forever=False)

        change = self._extract_change_from_call_args(pillow.processor.call_args)
        self.assertEqual(doc_id, change['id'])
        self.assertTrue(change.get('doc', None) is None)

    def test_couch_filter(self):
        pillow = BasicPillow(couch_db=self.couch_db)
        pillow.couch_filter = 'couchforms/xforms'
        self._apply_mocks_to_pillow(pillow)
        # save a random doc, then a form-looking thing
        self.couch_db.save_doc({'_id': uuid.uuid4().hex, 'property': 'property_value'})
        form = XFormInstance(domain='test-domain')
        form.save()
        pillow.process_changes(since=self.update_seq, forever=False)

        change = self._extract_change_from_call_args(pillow.processor.call_args)
        self.assertEqual(form._id, change['id'])
        self.assertEqual(form.domain, change['doc']['domain'])

    def _apply_mocks_to_pillow(self, pillow):
        pillow.processor = MagicMock(return_value=True)

    def _extract_change_from_call_args(self, call_args):
        ordered_args, keyword_args = call_args
        self.assertEqual(2, len(ordered_args))
        self.assertEqual(0, len(keyword_args))
        return ordered_args[0]
