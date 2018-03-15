from __future__ import absolute_import
from mock import patch
from datetime import datetime, timedelta

from corehq.apps.app_manager.models import Application
from corehq.apps.users.models import WebUser, CommCareUser
from corehq.apps.groups.models import Group
from corehq.apps.domain.models import Domain
from corehq.dbaccessors.couchapps.all_docs import delete_all_docs_by_doc_type
from corehq.warehouse.models import ApplicationStagingTable

from corehq.warehouse.tests.utils import create_batch, complete_batch, BaseWarehouseTestCase
from corehq.warehouse.models import (
    GroupStagingTable,
    DomainStagingTable,
    UserStagingTable,
    Batch,
)


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
        cls.batch = create_batch(cls.slug)

    def tearDown(self):
        self.staging_table_cls.clear_records()

    @classmethod
    def tearDownClass(cls):
        for record in cls.records:
            record.delete()
        super(BaseStagingTableTest, cls).tearDownClass()


class StagingRecordsTestsMixin(object):

    def test_stage_records(self):
        batch = self.batch

        self.assertEqual(self.staging_table_cls.objects.count(), 0)
        self.staging_table_cls.commit(batch)
        self.assertEqual(self.staging_table_cls.objects.count(), len(self.records))

        self.staging_table_cls.commit(batch)
        self.assertEqual(self.staging_table_cls.objects.count(), len(self.records))

    def test_stage_records_no_data(self):
        complete_batch(self.batch.id)
        batch = create_batch(self.slug)

        self.assertEqual(self.staging_table_cls.objects.count(), 0)
        self.staging_table_cls.commit(batch)
        self.assertEqual(self.staging_table_cls.objects.count(), 0)


class TestGroupStagingTable(BaseStagingTableTest, StagingRecordsTestsMixin):

    slug = 'group_dim'
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
        batch = self.batch

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

    slug = 'domain_dim'
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

    slug = 'user_dim'
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

    slug = 'app_dim'
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
