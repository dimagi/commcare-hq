import uuid

from django.test import TestCase

from casexml.apps.case.xml import V1
from casexml.apps.phone.exceptions import MissingSyncLog
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

    def test_previous_log_purged(self):
        device = MockDevice(self.project, self.restore_user)
        initial_sync = device.sync(items=True, version=V1, app=self.app)
        initial_synclog_id = initial_sync.restore_id
        self.assertIsNone(initial_sync.get_log().previous_log_id)

        # form submission success when there is no previous sync log
        form_xml = get_simple_form_xml(uuid.uuid4().hex)
        submit_form_locally(form_xml, self.domain, last_sync_token=initial_synclog_id)

        # second sync
        second_sync = device.sync(version=V1, app=self.app)
        third_sync = device.sync(version=V1, app=self.app)

        # form submission after second sync should remove first synclog
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
