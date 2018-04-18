from __future__ import absolute_import
from __future__ import unicode_literals
from mock import patch
from datetime import datetime, timedelta

from corehq.apps.app_manager.models import Application
from corehq.apps.users.models import WebUser, CommCareUser
from corehq.apps.groups.models import Group
from corehq.apps.domain.models import Domain
from corehq.dbaccessors.couchapps.all_docs import delete_all_docs_by_doc_type
from corehq.warehouse.models import ApplicationStagingTable

from corehq.warehouse.tests.utils import DEFAULT_BATCH_ID, get_default_batch, create_batch, BaseWarehouseTestCase
from corehq.warehouse.models import (
    GroupStagingTable,
    DomainStagingTable,
    UserStagingTable,
    Batch,
)


def setup_module():
    start = datetime.utcnow() - timedelta(days=3)
    end = datetime.utcnow() + timedelta(days=3)
    create_batch(start, end, DEFAULT_BATCH_ID)


def teardown_module():
    Batch.objects.all().delete()


class BaseStagingTableTest(BaseWarehouseTestCase):
    records = []
    staging_table_cls = None

    @classmethod
    def setUpClass(cls):
        super(BaseStagingTableTest, cls).setUpClass()
        for record in cls.records:
            record.save()

    def tearDown(self):
        self.staging_table_cls.clear_records()

    @classmethod
    def tearDownClass(cls):
        for record in cls.records:
            record.delete()
        super(BaseStagingTableTest, cls).tearDownClass()


class StagingRecordsTestsMixin(object):

    def test_stage_records(self):
        batch = get_default_batch()

        self.assertEqual(self.staging_table_cls.objects.count(), 0)
        self.staging_table_cls.commit(batch)
        self.assertEqual(self.staging_table_cls.objects.count(), len(self.records))

        self.staging_table_cls.commit(batch)
        self.assertEqual(self.staging_table_cls.objects.count(), len(self.records))

    def test_stage_records_no_data(self):
        start = datetime.utcnow() - timedelta(days=3)
        end = datetime.utcnow() - timedelta(days=2)
        batch = create_batch(start, end)

        self.assertEqual(self.staging_table_cls.objects.count(), 0)
        self.staging_table_cls.commit(batch)
        self.assertEqual(self.staging_table_cls.objects.count(), 0)


class TestGroupStagingTable(BaseStagingTableTest, StagingRecordsTestsMixin):

    records = [
        Group(domain='group-staging-test', name='one', case_sharing=True, reporting=True),
        Group(domain='group-staging-test', name='two'),
        Group(domain='group-staging-test', name='three'),
    ]
    staging_table_cls = GroupStagingTable

    @classmethod
    def setUpClass(cls):
        delete_all_docs_by_doc_type(Group.get_db(), ['Group', 'Group-Deleted'])
        super(TestGroupStagingTable, cls).setUpClass()

    def test_stage_records_bulk(self):
        batch = get_default_batch()

        # 1 Query for clearing records
        # 1 Query for inserting recorrds
        with self.assertNumQueries(2, using=self.using):
            GroupStagingTable.commit(batch)

        # 1 Query for clearing records
        # 2 Queries for inserting recorrds
        with self.assertNumQueries(3, using=self.using):
            with patch('corehq.warehouse.utils.DJANGO_MAX_BATCH_SIZE', 2):
                GroupStagingTable.commit(batch)
        self.assertEqual(GroupStagingTable.objects.count(), 3)


class TestDomainStagingTable(BaseStagingTableTest, StagingRecordsTestsMixin):

    records = [
        Domain(name='one', hr_name='One', creating_user_id='abc', is_active=True),
        Domain(name='two', is_active=True),
        Domain(name='three', is_active=True),
    ]
    staging_table_cls = DomainStagingTable

    @classmethod
    def setUpClass(cls):
        delete_all_docs_by_doc_type(Domain.get_db(), ['Domain', 'Domain-Deleted'])
        super(TestDomainStagingTable, cls).setUpClass()


class TestUserStagingTable(BaseStagingTableTest, StagingRecordsTestsMixin):

    records = [
        # TODO: Make domains compatible with staging table
        # WebUser(
        #     username='one',
        #     date_joined=datetime.utcnow(),
        #     first_name='A',
        #     last_name='B',
        #     email='b@a.com',
        #     password='***',
        #     is_active=True,
        #     is_staff=False,
        #     is_superuser=True,
        # ),
        CommCareUser(
            domain='foo',
            username='two',
            date_joined=datetime.utcnow(),
            email='a@a.com',
            password='***',
            is_active=True,
            is_staff=True,
            is_superuser=False,
        ),
    ]
    staging_table_cls = UserStagingTable

    @classmethod
    def setUpClass(cls):
        delete_all_docs_by_doc_type(WebUser.get_db(), ['CommCareUser', 'WebUser'])
        super(TestUserStagingTable, cls).setUpClass()


class TestAppStagingTable(BaseStagingTableTest, StagingRecordsTestsMixin):

    records = [
        Application(
            domain='test',
            name='test-app',
        ),
        Application(
            domain='test',
            name='deleted-app',
            doc_type='Application-Deleted'
        )
    ]
    staging_table_cls = ApplicationStagingTable

    @classmethod
    def setUpClass(cls):
        delete_all_docs_by_doc_type(Application.get_db(), ['Application', 'Application-Deleted'])
        super(TestAppStagingTable, cls).setUpClass()
