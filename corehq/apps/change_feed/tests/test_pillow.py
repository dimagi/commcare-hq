from django.test import SimpleTestCase
from corehq.apps.change_feed.pillow import ChangeFeedPillow
from pillowtop.feed.interface import Change


class ChangeFeedPillowTest(SimpleTestCase):

    def test_process_change(self):
        pillow = ChangeFeedPillow()
        document = {
            'doc_type': 'CommCareCase',
            'type': 'mother',
            'domain': 'kafka-test-domain',
        }
        pillow.process_change(Change(id='test', sequence_id='3', document=document))
