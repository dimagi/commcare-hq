import uuid

from django.test import TestCase

from casexml.apps.case.xml import V1
from casexml.apps.phone.models import SyncLogSQL
from casexml.apps.phone.restore import RestoreConfig, RestoreParams
from casexml.apps.phone.tests.utils import create_restore_user
from casexml.apps.phone.utils import MockDevice

from corehq.apps.app_manager.models import Application
from corehq.apps.domain.models import Domain


class SyncLogModelTest(TestCase):
    domain = 'sync-log-model-test'

    @classmethod
    def setUpClass(cls):
        super(SyncLogModelTest, cls).setUpClass()
        cls.project = Domain(name=cls.domain)
        cls.project.save()
        cls.restore_user = create_restore_user(cls.domain, username=uuid.uuid4().hex)

    @classmethod
    def tearDownClass(cls):
        cls.project.delete()
        super(SyncLogModelTest, cls).tearDownClass()

    def test_basic_properties(self):
        # kick off a restore to generate the sync log
        device = MockDevice(self.project, self.restore_user)
        sync_log = device.sync(version=V1, items=True).log
        self.assertEqual(self.restore_user.user_id, sync_log.user_id)
        self.assertEqual(self.restore_user.domain, sync_log.domain)

    def test_build_id(self):
        app = Application(domain=self.domain)
        app.save()
        config = RestoreConfig(
            project=self.project,
            restore_user=self.restore_user,
            params=RestoreParams(
                app=app,
            ),
        )
        config.get_payload()  # this generates the sync log
        sync_log = SyncLogSQL.objects.filter(
            user_id=self.restore_user.user_id
        ).order_by('date').last()
        self.assertEqual(self.restore_user.user_id, sync_log.user_id)
        self.assertEqual(self.restore_user.domain, sync_log.domain)
        self.assertEqual(app._id, sync_log.build_id)
        self.addCleanup(app.delete)
