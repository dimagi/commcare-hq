import uuid

from django.test import TestCase
from testil import eq

from casexml.apps.case.xml import V1
from casexml.apps.phone.exceptions import MissingSyncLog
from casexml.apps.phone.models import get_alt_device_id
from casexml.apps.phone.tests.utils import create_restore_user
from casexml.apps.phone.utils import MockDevice

from corehq.apps.app_manager.models import Application
from corehq.apps.domain.models import Domain
from corehq.apps.receiverwrapper.util import submit_form_locally
from corehq.form_processor.tests.utils import FormProcessorTestUtils
from corehq.form_processor.utils import get_simple_form_xml


class TestSyncPurge(TestCase):
    @classmethod
    def setUpClass(cls):
        super(TestSyncPurge, cls).setUpClass()
        cls.domain = uuid.uuid4().hex
        cls.project = Domain(name=cls.domain)
        cls.project.save()
        cls.restore_user = create_restore_user(domain=cls.domain)
        cls.app = Application(domain=cls.domain)
        cls.app.save()

    @classmethod
    def tearDownClass(cls):
        FormProcessorTestUtils.delete_all_xforms(cls.domain)
        FormProcessorTestUtils.delete_all_sync_logs()
        cls.project.delete()
        super(TestSyncPurge, cls).tearDownClass()

    def test_prune_synclogs(self):
        device = MockDevice(self.project, self.restore_user)
        initial_sync = device.sync(items=True, version=V1, app=self.app)
        initial_synclog_id = initial_sync.restore_id
        self.assertIsNone(initial_sync.get_log().previous_log_id)

        # form submission success when there is no previous sync log
        form_xml = get_simple_form_xml(uuid.uuid4().hex)
        submit_form_locally(form_xml, self.domain, last_sync_token=initial_synclog_id)

        # more syncs
        second_sync = device.sync(version=V1, app=self.app)
        third_sync = device.sync(version=V1, app=self.app)

        # form submission should remove all previous syncs
        form_xml = get_simple_form_xml(uuid.uuid4().hex)
        submit_form_locally(form_xml, self.domain, last_sync_token=third_sync.restore_id)

        third_synclog = third_sync.get_log()  # re-fetch
        self.assertIsNone(third_synclog.previous_log_id)

        with self.assertRaises(MissingSyncLog):
            initial_sync.get_log()

        with self.assertRaises(MissingSyncLog):
            second_sync.get_log()

        # form submissions after purge don't fail
        form_xml = get_simple_form_xml(uuid.uuid4().hex)
        submit_form_locally(form_xml, self.domain, last_sync_token=third_sync.restore_id)

        # restores after purge don't fail
        fourth_sync = device.sync(version=V1, app=self.app)
        response = fourth_sync.config.get_response()
        self.assertEqual(response.status_code, 200)

    def test_prune_formplayer_synclogs(self):
        device = MockDevice(self.project, self.restore_user)
        device.id = 'WebAppsLogin-' + device.id
        first_sync = device.sync()
        second_sync = device.sync()
        third_sync = device.sync()

        device2 = MockDevice(self.project, self.restore_user)
        device2.id = 'WebAppsLogin-' + device2.id
        other_sync = device2.sync()

        form_xml = get_simple_form_xml(uuid.uuid4().hex)
        submit_form_locally(form_xml, self.domain, last_sync_token=third_sync.restore_id)

        self.assertIsNone(third_sync.get_log().previous_log_id)

        with self.assertRaises(MissingSyncLog):
            first_sync.get_log()

        with self.assertRaises(MissingSyncLog):
            second_sync.get_log()

        # Other sync for same user but with different device ID is still there
        self.assertIsNotNone(other_sync.get_log())

        # form submissions after purge don't fail
        form_xml = get_simple_form_xml(uuid.uuid4().hex)
        submit_form_locally(form_xml, self.domain, last_sync_token=third_sync.restore_id)

        # restores after purge don't fail
        fourth_sync = device.sync()
        response = fourth_sync.config.get_response()
        self.assertEqual(response.status_code, 200)


def test_get_alt_device_id():
    eq(get_alt_device_id('WebAppsLogin*mr.snuggles@example.com*as*example.mr.snuggles'),
                         'WebAppsLogin*mr_snuggles@example_com*as*example.mr.snuggles')
