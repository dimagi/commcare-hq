from __future__ import absolute_import
import uuid

from django.test import TestCase

from casexml.apps.case.xml import V1
from casexml.apps.phone.exceptions import MissingSyncLog
from casexml.apps.phone.tests.utils import create_restore_user
from casexml.apps.phone.utils import MockDevice
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

    @classmethod
    def tearDownClass(cls):
        FormProcessorTestUtils.delete_all_xforms(cls.domain)
        FormProcessorTestUtils.delete_all_sync_logs()
        cls.project.delete()
        super(TestSyncPurge, cls).tearDownClass()

    def test_previous_log_purged(self):
        device = MockDevice(self.project, self.restore_user)
        initial_sync = device.sync(items=True, version=V1)
        initial_synclog_id = initial_sync.restore_id

        # form submission success when there is no previous sync log
        form_xml = get_simple_form_xml(uuid.uuid4().hex)
        submit_form_locally(form_xml, self.domain, last_sync_token=initial_synclog_id)

        # second sync
        second_sync = device.sync(version=V1)
        synclog_id = second_sync.restore_id

        synclog = second_sync.get_log()
        self.assertEqual(synclog.previous_log_id, initial_synclog_id)
        self.assertFalse(synclog.previous_log_removed)

        # form submission after second sync should remove first synclog
        form_xml = get_simple_form_xml(uuid.uuid4().hex)
        submit_form_locally(form_xml, self.domain, last_sync_token=synclog_id)

        synclog = second_sync.get_log()
        self.assertEqual(synclog.previous_log_id, initial_synclog_id)
        self.assertTrue(synclog.previous_log_removed)

        with self.assertRaises(MissingSyncLog):
            initial_sync.get_log()

        # form submissions after purge don't fail
        form_xml = get_simple_form_xml(uuid.uuid4().hex)
        submit_form_locally(form_xml, self.domain, last_sync_token=synclog_id)

        # restores after purge don't fail
        third_sync = device.sync(version=V1)
        response = third_sync.config.get_response()
        self.assertEqual(response.status_code, 200)
