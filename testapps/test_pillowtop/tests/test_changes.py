import uuid
from django.test import TestCase
from mock import MagicMock
from couchforms.models import XFormInstance
from pillowtop.feed.couch import get_current_seq
from pillowtop.tests.utils import FakeConstructedPillow


class ChangeFeedDbTest(TestCase):

    def setUp(self):
        super(ChangeFeedDbTest, self).setUp()
        self.couch_db = XFormInstance.get_db()
        self.update_seq = get_current_seq(self.couch_db)

    def test_basic_functionality(self):
        pillow = _make_couch_pillow(self.couch_db)
        doc_id = uuid.uuid4().hex
        self.couch_db.save_doc({'_id': doc_id, 'property': 'property_value'})
        pillow.process_changes(since=self.update_seq, forever=False)

        change = self._extract_change_from_call_args(pillow.process_change.call_args)
        # validate the structure of the change. some implicit asserts here
        self.assertEqual(doc_id, change['id'])
        doc = change['doc']
        self.assertEqual(doc_id, doc['_id'])
        self.assertEqual('property_value', doc['property'])

    def test_include_docs_false(self):
        pillow = _make_couch_pillow(self.couch_db, include_docs=False)
        doc_id = uuid.uuid4().hex
        self.couch_db.save_doc({'_id': doc_id, 'property': 'property_value'})
        pillow.process_changes(since=self.update_seq, forever=False)

        change = self._extract_change_from_call_args(pillow.process_change.call_args)
        self.assertEqual(doc_id, change['id'])
        self.assertTrue(change.get('doc', None) is None)

    def test_couch_filter(self):
        from time import sleep

        pillow = _make_couch_pillow(self.couch_db)
        pillow.couch_filter = 'couchforms/xforms'
        # save a random doc, then a form-looking thing
        self.couch_db.save_doc({'_id': uuid.uuid4().hex, 'property': 'property_value'})
        form = XFormInstance(domain='test-domain')
        form.save()
        sleep(1)
        pillow.process_changes(since=self.update_seq, forever=False)

        change = self._extract_change_from_call_args(pillow.process_change.call_args)
        self.assertEqual(form._id, change['id'])
        self.assertEqual(form.domain, change['doc']['domain'])

    def _extract_change_from_call_args(self, call_args):
        ordered_args, keyword_args = call_args
        self.assertEqual(1, len(ordered_args))
        self.assertEqual(0, len(keyword_args))
        return ordered_args[0]


def _make_couch_pillow(couch_db, include_docs=True):
    from pillowtop.feed.couch import CouchChangeFeed
    from pillowtop.processors import LoggingProcessor
    from pillowtop.checkpoints.manager import PillowCheckpoint

    pillow = FakeConstructedPillow(
        name='fake-couch-pillow',
        checkpoint=PillowCheckpoint('fake-feed-test-checkpoint'),
        change_feed=CouchChangeFeed(couch_db=couch_db, include_docs=include_docs),
        processor=LoggingProcessor(),
    )
    pillow.process_change = MagicMock(return_value=True)
    return pillow
