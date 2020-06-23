import uuid

from django.test import SimpleTestCase

from corehq.util.es.elasticsearch import ConnectionError
from mock import MagicMock, patch

from dimagi.utils.couch.undo import DELETED_SUFFIX
# Also, you need to patch the path to the function in the file where the signal
# handler uses it, not where it's actually defined.  That's quite a gotcha.
from pillowtop.es_utils import initialize_index_and_mapping

from corehq.apps.reports.analytics.esaccessors import get_user_stubs
from corehq.elastic import doc_exists_in_es, get_es_new
from corehq.pillows.mappings.user_mapping import USER_INDEX_INFO
from corehq.util.test_utils import mock_out_couch, trap_extra_setup

from ..models import CommCareUser, WebUser

# Note that you can't directly patch the signal handler, as that code has
# already been called.  It's easier to patch something that the handler calls.



@mock_out_couch()
@patch('corehq.apps.users.models.CouchUser.sync_to_django_user', new=MagicMock())
@patch('corehq.apps.users.models.CommCareUser.project', new=MagicMock())
class TestUserSignals(SimpleTestCase):

    @patch('corehq.apps.analytics.signals.update_hubspot_properties.delay')
    @patch('corehq.apps.callcenter.tasks.sync_user_cases')
    @patch('corehq.apps.cachehq.signals.invalidate_document')
    @patch('corehq.apps.users.signals.send_to_elasticsearch')
    @patch('corehq.apps.users.signals._should_sync_to_es', return_value=True)
    def test_commcareuser_save(self, _, send_to_es, invalidate,
                               sync_user_cases, update_hubspot_properties):
        CommCareUser(username='test').save()

        self.assertTrue(send_to_es.called)
        self.assertTrue(invalidate.called)
        self.assertTrue(sync_user_cases.called)
        self.assertFalse(update_hubspot_properties.called)

    @patch('corehq.apps.analytics.signals.update_hubspot_properties.delay')
    @patch('corehq.apps.callcenter.tasks.sync_user_cases')
    @patch('corehq.apps.cachehq.signals.invalidate_document')
    @patch('corehq.apps.users.signals.send_to_elasticsearch')
    @patch('corehq.apps.users.signals._should_sync_to_es', return_value=True)
    def test_webuser_save(self, _, send_to_es, invalidate,
                          sync_user_cases, update_hubspot_properties):
        WebUser().save()

        self.assertTrue(send_to_es.called)
        self.assertTrue(invalidate.called)
        self.assertFalse(sync_user_cases.called)
        self.assertTrue(update_hubspot_properties.called)


@mock_out_couch()
@patch('corehq.apps.users.models.CouchUser.sync_to_django_user', new=MagicMock)
@patch('corehq.apps.analytics.signals.update_hubspot_properties')
@patch('corehq.apps.callcenter.tasks.sync_user_cases')
@patch('corehq.apps.cachehq.signals.invalidate_document')
@patch('corehq.apps.users.signals._should_sync_to_es', return_value=True)
class TestUserSyncToEs(SimpleTestCase):

    @classmethod
    def setUpClass(cls):
        super(TestUserSyncToEs, cls).setUpClass()

        # create the index
        cls.es = get_es_new()
        with trap_extra_setup(ConnectionError):
            initialize_index_and_mapping(cls.es, USER_INDEX_INFO)

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
        self.es.indices.refresh(USER_INDEX_INFO.index)
        self.assertFalse(doc_exists_in_es(USER_INDEX_INFO, user._id))

    def check_user(self, user):
        self.es.indices.refresh(USER_INDEX_INFO.index)
        results = get_user_stubs([user._id])
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0], {
            '_id': user._id,
            'username': user.username,
            'is_active': True,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'doc_type': user.doc_type,
            'location_id': 'location1',
            '__group_ids': []
        })
