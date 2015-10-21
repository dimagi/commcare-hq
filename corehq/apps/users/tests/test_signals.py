from django.test import SimpleTestCase
from mock import patch

from corehq.util.test_utils import mock_out_couch

from ..models import CommCareUser

# Note that you can't directly patch the signal handler, as that code has
# already been called.  It's easier to patch something that the handler calls.

# Also, you need to patch the path to the function in the file where the signal
# handler uses it, not where it's actually defined.  That's quite a gotcha.


@mock_out_couch()
class TestUserSignals(SimpleTestCase):

    @patch('corehq.apps.callcenter.signals.sync_call_center_user_case')
    @patch('corehq.apps.cachehq.signals.invalidate_document')
    @patch('corehq.apps.users.signals.send_to_elasticsearch')
    def test_commcareuser_save(self, send_to_es, invalidate, sync_call_center):
        CommCareUser.create("test-domain", "test-username", "guest")

        self.assertTrue(send_to_es.called)
        self.assertTrue(invalidate.called)
        self.assertTrue(sync_call_center.called)
