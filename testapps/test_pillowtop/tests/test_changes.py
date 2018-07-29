from __future__ import absolute_import
from __future__ import unicode_literals
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

        changes = self._extract_changes_from_call_args(pillow.process_change.call_args_list)
        change_ids = {change['id'] for change in changes}
        # validate the structure of the change. some implicit asserts here
        self.assertIn(doc_id, change_ids)
        doc = [change['doc'] for change in changes if change['doc']['_id'] == doc_id][0]
        self.assertEqual(doc_id, doc['_id'])
        self.assertEqual('property_value', doc['property'])

    def test_couch_filter(self):
        pillow = _make_couch_pillow(self.couch_db)
        pillow.couch_filter = 'couchforms/xforms'
        # save a random doc, then a form-looking thing
        self.couch_db.save_doc({'_id': uuid.uuid4().hex, 'property': 'property_value'})
        form = XFormInstance(domain='test-domain')
        form.save()
        pillow.process_changes(since=self.update_seq, forever=False)

        changes = self._extract_changes_from_call_args(pillow.process_change.call_args_list)
        change_ids = {change['id'] for change in changes}
        change_domains = {change['doc'].get('domain', None) for change in changes}
        self.assertIn(form._id, change_ids)
        self.assertIn(form.domain, change_domains)

    def _extract_changes_from_call_args(self, call_args_list):
        ret = []
        for call_args in call_args_list:
            ordered_args, keyword_args = call_args
            self.assertEqual(1, len(ordered_args))
            self.assertEqual(0, len(keyword_args))
            ret.append(ordered_args[0])
        return ret


def _make_couch_pillow(couch_db):
    from pillowtop.feed.couch import CouchChangeFeed
    from pillowtop.processors import LoggingProcessor
    from pillowtop.checkpoints.manager import PillowCheckpoint

    pillow = FakeConstructedPillow(
        name='fake-couch-pillow',
        checkpoint=PillowCheckpoint('fake-feed-test-checkpoint', 'text'),
        change_feed=CouchChangeFeed(couch_db=couch_db),
        processor=LoggingProcessor(),
    )
    pillow.process_change = MagicMock(return_value=True)
    return pillow
