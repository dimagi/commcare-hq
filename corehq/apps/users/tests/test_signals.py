import uuid
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from dimagi.utils.couch.undo import DELETED_SUFFIX

from corehq.apps.es.client import manager
from corehq.apps.es.tests.utils import es_test
from corehq.apps.es.users import user_adapter
from corehq.apps.reports.analytics.esaccessors import get_user_stubs
from corehq.apps.users.tests.util import patch_user_data_db_layer
from corehq.util.es.testing import sync_users_to_es
from corehq.util.test_utils import mock_out_couch

from ..models import CommCareUser, WebUser
from ..signals import update_user_in_es

# Note that you can't directly patch the signal handler, as that code has
# already been called.  It's easier to patch something that the handler calls.

# Also, you need to patch the path to the function in the file where the signal
# handler uses it, not where it's actually defined.  That's quite a gotcha.


@mock_out_couch()
@patch('corehq.apps.sms.tasks.sync_user_phone_numbers', new=MagicMock())
@patch('corehq.apps.users.models.CouchUser.sync_to_django_user', new=MagicMock())
@patch('corehq.apps.users.models.CommCareUser.project', new=MagicMock())
@es_test
class TestUserSignals(SimpleTestCase):

    @patch('corehq.apps.analytics.signals.update_hubspot_properties.delay')
    @patch('corehq.apps.callcenter.tasks.sync_usercases')
    @patch('corehq.apps.cachehq.signals.invalidate_document')
    @patch('corehq.apps.users.signals._update_user_in_es')
    def test_commcareuser_save(self, send_to_es, invalidate, sync_usercases,
                               update_hubspot_properties):
        CommCareUser(username='test').save()

        self.assertTrue(send_to_es.called)
        self.assertTrue(invalidate.called)
        self.assertTrue(sync_usercases.called)
        self.assertFalse(update_hubspot_properties.called)

    @patch('corehq.apps.analytics.signals.update_hubspot_properties.delay')
    @patch('corehq.apps.callcenter.tasks.sync_usercases')
    @patch('corehq.apps.cachehq.signals.invalidate_document')
    @patch('corehq.apps.users.signals._update_user_in_es')
    def test_webuser_save(self, send_to_es, invalidate, sync_usercases,
                          update_hubspot_properties):
        WebUser().save()

        self.assertTrue(send_to_es.called)
        self.assertTrue(invalidate.called)
        self.assertFalse(sync_usercases.called)
        self.assertTrue(update_hubspot_properties.called)


@mock_out_couch()
@patch_user_data_db_layer()
@patch('corehq.apps.users.models.CouchUser.sync_to_django_user', new=MagicMock)
@patch('corehq.apps.analytics.signals.update_hubspot_properties')
@patch('corehq.apps.callcenter.tasks.sync_usercases')
@patch('corehq.apps.cachehq.signals.invalidate_document')
@es_test(requires=[user_adapter], setup_class=True)
class TestUserSyncToEs(SimpleTestCase):

    @sync_users_to_es()
    def test_sync_to_es_create_update_delete(self, *mocks):
        domain = 'user_es_domain'
        user = CommCareUser(
            domain=domain,
            username='user1',
            _id=uuid.uuid4().hex,
            is_active=True,
            first_name='user1 first name',
            last_name='user1 last name',
            location_id='location1'
        )
        user.save()

        self.check_user(user)

        user.first_name = 'new first name'
        user.save()
        self.check_user(user)

        # simulate retire without needing couch
        user.base_doc += DELETED_SUFFIX
        user.save()
        manager.index_refresh(user_adapter.index_name)
        self.assertFalse(user_adapter.exists(user._id))

    def check_user(self, user):
        manager.index_refresh(user_adapter.index_name)
        results = get_user_stubs([user._id])
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0], {
            '_id': user._id,
            'domain': user.domain,
            'username': user.username,
            'is_active': True,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'doc_type': user.doc_type,
            'location_id': 'location1',
            '__group_ids': []
        })


@es_test(requires=[user_adapter])
class TestElasticSyncPatch(SimpleTestCase):

    class MockUser:
        user_id = "ab12"

        def to_be_deleted(self):
            return False

        def to_json(self):
            return {"_id": self.user_id, "username": "test"}

    def test_user_sync_is_disabled_by_default_during_unittests(self):
        user = self.MockUser()
        self.assertFalse(user_adapter.exists(user.user_id))
        update_user_in_es(None, user)
        self.assertFalse(user_adapter.exists(user.user_id))

    @sync_users_to_es()
    def test_user_sync_is_enabled_with_decorator(self):
        def simple_doc(user):
            user_json = user.to_json()
            return (user_json.pop('_id'), user_json)
        user = self.MockUser()
        self.assertFalse(user_adapter.exists(user.user_id))
        with patch.object(user_adapter, 'from_python', simple_doc):
            update_user_in_es(None, user)
        self.assertTrue(user_adapter.exists(user.user_id))
