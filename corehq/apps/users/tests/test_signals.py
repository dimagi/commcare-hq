from django.test import SimpleTestCase
from mock import patch, MagicMock

from corehq.util.test_utils import mock_out_couch

from ..models import CommCareUser, WebUser

# Note that you can't directly patch the signal handler, as that code has
# already been called.  It's easier to patch something that the handler calls.

# Also, you need to patch the path to the function in the file where the signal
# handler uses it, not where it's actually defined.  That's quite a gotcha.


@mock_out_couch()
@patch('corehq.apps.users.models.CouchUser.sync_to_django_user', new=MagicMock)
class TestUserSignals(SimpleTestCase):

    @patch('corehq.apps.analytics.signals.update_hubspot_properties')
    @patch('corehq.apps.callcenter.signals.sync_call_center_user_case')
    @patch('corehq.apps.cachehq.signals.invalidate_document')
    @patch('corehq.apps.users.signals.send_to_elasticsearch')
    def test_commcareuser_save(self, send_to_es, invalidate, sync_call_center,
                               update_hubspot_properties):
        CommCareUser().save()

        self.assertTrue(send_to_es.called)
        self.assertTrue(invalidate.called)
        self.assertTrue(sync_call_center.called)
        self.assertFalse(update_hubspot_properties.called)

    @patch('corehq.apps.analytics.signals.update_hubspot_properties')
    @patch('corehq.apps.callcenter.signals.sync_call_center_user_case')
    @patch('corehq.apps.cachehq.signals.invalidate_document')
    @patch('corehq.apps.users.signals.send_to_elasticsearch')
    def test_webuser_save(self, send_to_es, invalidate, sync_call_center,
                          update_hubspot_properties):
        WebUser().save()

        self.assertTrue(send_to_es.called)
        self.assertTrue(invalidate.called)
        self.assertFalse(sync_call_center.called)
        self.assertTrue(update_hubspot_properties.called)
