import uuid

from couchdbkit.exceptions import ResourceNotFound
from django.test import TestCase

from casexml.apps.phone.models import get_properly_wrapped_sync_log
from casexml.apps.phone.tests.utils import create_restore_user, deprecated_generate_restore_payload, \
    deprecated_synclog_id_from_restore_payload, generate_restore_response
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
        initial_synclog_id = deprecated_synclog_id_from_restore_payload(
            deprecated_generate_restore_payload(self.project, self.restore_user, items=True)
        )

        # form submission success when there is no previous sync log
        form_xml = get_simple_form_xml(uuid.uuid4().hex)
        submit_form_locally(form_xml, self.domain, last_sync_token=initial_synclog_id)

        # second sync
        synclog_id = deprecated_synclog_id_from_restore_payload(
            deprecated_generate_restore_payload(
                self.project, self.restore_user, restore_id=initial_synclog_id))

        synclog = get_properly_wrapped_sync_log(synclog_id)
        self.assertEqual(synclog.previous_log_id, initial_synclog_id)
        self.assertFalse(synclog.previous_log_removed)

        # form submission after second sync should remove first synclog
        form_xml = get_simple_form_xml(uuid.uuid4().hex)
        submit_form_locally(form_xml, self.domain, last_sync_token=synclog_id)

        synclog = get_properly_wrapped_sync_log(synclog_id)
        self.assertEqual(synclog.previous_log_id, initial_synclog_id)
        self.assertTrue(synclog.previous_log_removed)

        with self.assertRaises(ResourceNotFound):
            get_properly_wrapped_sync_log(initial_synclog_id)

        # form submissions after purge don't fail
        form_xml = get_simple_form_xml(uuid.uuid4().hex)
        submit_form_locally(form_xml, self.domain, last_sync_token=synclog_id)

        # restores after purge don't fail
        response = generate_restore_response(
            self.project, self.restore_user, restore_id=synclog_id
        )
        self.assertEqual(response.status_code, 200)
