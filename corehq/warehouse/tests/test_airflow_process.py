import uuid
from datetime import datetime, timedelta

from django.core.management import call_command

from corehq.apps.users.models import CommCareUser, WebUser
from corehq.dbaccessors.couchapps.all_docs import delete_all_docs_by_doc_type
from corehq.warehouse.loaders import UserDimLoader, UserStagingLoader
from corehq.warehouse.models import Batch, CommitRecord
from corehq.warehouse.tests.utils import BaseWarehouseTestCase


class TestUserLoad(BaseWarehouseTestCase):
    @classmethod
    def setUpClass(cls):
        super(TestUserLoad, cls).setUpClass()
        delete_all_docs_by_doc_type(WebUser.get_db(), ['CommCareUser', 'WebUser'])
        cls.user = CommCareUser.create(
            'test_domain',
            'commcare-user',
            '***',
            date_joined=datetime.utcnow(),
            email='a@a.com',
            is_active=True,
            is_staff=True,
            is_superuser=False,
        )

    @classmethod
    def tearDownClass(cls):
        cls.user.delete()
        UserStagingLoader().clear_records()
        UserDimLoader().clear_records()
        CommitRecord.objects.all().delete()
        Batch.objects.all().delete()
        super(TestUserLoad, cls).tearDownClass()

    def test_load(self):
        batch_slug = uuid.uuid4().hex

        # add 1 second to make sure we are after the user modification time
        end = datetime.utcnow() + timedelta(seconds=1)
        call_command('create_batch', batch_slug, end.strftime('%Y-%m-%d %H:%M:%S'))
        batch = Batch.objects.get(dag_slug=batch_slug)

        self._commit_table_assert_count(UserStagingLoader, batch, 1)
        self._commit_table_assert_count(UserDimLoader, batch, 1)

        call_command('mark_batch_complete', batch.id)
        batch = Batch.objects.get(dag_slug=batch_slug)
        self.assertIsNotNone(batch.completed_on)

    def _commit_table_assert_count(self, loader, batch, expected_count):
        call_command('commit_table', loader.slug, batch.id)
        commit_record = CommitRecord.objects.get(batch=batch, slug=loader.slug)
        self.assertTrue(commit_record.verified)
        self.assertTrue(commit_record.success)
        self.assertEqual(loader.model_cls.objects.count(), expected_count)
