from __future__ import absolute_import
from datetime import datetime, timedelta

from corehq.apps.users.util import SYSTEM_USER_ID, DEMO_USER_ID
from corehq.apps.commtrack.const import COMMTRACK_USERNAME
from corehq.pillows.utils import (
    SYSTEM_USER_TYPE,
    DEMO_USER_TYPE,
    COMMCARE_SUPPLY_USER_TYPE,
    WEB_USER_TYPE,
    MOBILE_USER_TYPE,
)
from corehq.warehouse.models import ApplicationDim
from corehq.warehouse.models import ApplicationStagingTable
from corehq.warehouse.tests.utils import (
    create_user_staging_record,
    create_location_records_from_tree,
    create_location_staging_record,
    create_group_staging_record,
    create_batch,
    BaseWarehouseTestCase, create_application_staging_record)
from corehq.warehouse.models import (
    Batch,
    UserStagingTable,
    UserDim,
    GroupStagingTable,
    GroupDim,
    UserGroupDim,
    LocationDim,
    LocationStagingTable,
    DomainMembershipDim
)


def teardown_module():
    Batch.objects.all().delete()


class TestUserDim(BaseWarehouseTestCase):

    domain = 'user-dim-test'
    slug = 'user_dim'

    @classmethod
    def setUpClass(cls):
        super(TestUserDim, cls).setUpClass()
        cls.batch = create_batch(cls.slug)
        cls.records = [
            create_user_staging_record(
                cls.domain,
                user_id=SYSTEM_USER_ID,
                username='system_bob',
                batch_id=cls.batch.id
            ),
            create_user_staging_record(
                cls.domain,
                user_id=DEMO_USER_ID,
                username='demo_sally',
                batch_id=cls.batch.id
            ),
            create_user_staging_record(
                cls.domain,
                user_id=COMMTRACK_USERNAME,
                username='commtrack_billy',
                batch_id=cls.batch.id
            ),
            create_user_staging_record(
                None,
                user_id='beeboobop',
                username='web',
                doc_type='WebUser',
                batch_id=cls.batch.id
            ),
            create_user_staging_record(
                cls.domain,
                user_id='greengoblin',
                username='mobile',
                batch_id=cls.batch.id
            ),
        ]

    @classmethod
    def tearDownClass(cls):
        for record in cls.records:
            record.delete()
        UserDim.clear_records()
        UserStagingTable.clear_records()
        super(TestUserDim, cls).tearDownClass()

    def test_user_types(self):
        UserDim.commit(self.batch)

        self.assertEqual(UserDim.objects.count(), 5)
        self.assertEqual(
            UserDim.objects.filter(user_type=SYSTEM_USER_TYPE).first().user_id,
            SYSTEM_USER_ID,
        )
        self.assertEqual(
            UserDim.objects.filter(user_type=DEMO_USER_TYPE).first().user_id,
            DEMO_USER_ID,
        )
        self.assertEqual(
            UserDim.objects.filter(user_type=COMMCARE_SUPPLY_USER_TYPE).first().user_id,
            COMMTRACK_USERNAME,
        )
        self.assertEqual(
            UserDim.objects.filter(user_type=MOBILE_USER_TYPE).first().user_id,
            'greengoblin',
        )
        self.assertEqual(
            UserDim.objects.filter(user_type=WEB_USER_TYPE).first().user_id,
            'beeboobop',
        )


class TestDomainMembershipDim(BaseWarehouseTestCase):
    slug = DomainMembershipDim.slug

    @classmethod
    def setUpClass(cls):
        super(TestDomainMembershipDim, cls).setUpClass()
        cls.batch = create_batch(cls.slug)
        cls.bootstrap_user_staging()

    @classmethod
    def bootstrap_user_staging(cls):
        create_user_staging_record(
            domain='test1',
            user_id='u1',
            username='mobile1',
            doc_type='CommCareUser',
            batch_id=cls.batch.id,
        )
        create_user_staging_record(
            domain='test1',
            user_id='u2',
            username='mobile2',
            doc_type='CommCareUser',
            batch_id=cls.batch.id,
        )
        create_user_staging_record(
            domain=None,
            username='mobile1',
            user_id='u3',
            doc_type='WebUser',
            batch_id=cls.batch.id,
            domain_memberships=[
                {'domain': 'test1', 'is_admin': True},
                {'domain': 'test2', 'is_admin': False},
            ]
        )
        UserDim.commit(cls.batch)

    @classmethod
    def tearDownClass(cls):
        DomainMembershipDim.clear_records()
        UserDim.clear_records()
        UserStagingTable.clear_records()
        super(TestDomainMembershipDim, cls).tearDownClass()

    def test_insert_and_update(self):
        DomainMembershipDim.commit(self.batch)
        # should create 4 domain membership columns
        self.assertEqual(
            DomainMembershipDim.objects.count(), 4
        )
        # 'u3' user should have 2 membership columns for each of the domain
        dim_id_of_user3 = UserDim.objects.filter(user_id='u3')[0].id
        self.assertEqual(
            DomainMembershipDim.objects.filter(user_dim_id=dim_id_of_user3).count(),
            2
        )

        ## test removing a domain membership
        # clear and add new staging record to remove a membership of 2
        UserStagingTable.clear_records()
        create_user_staging_record(
            domain=None,
            username='mobile1',
            user_id='u3',
            doc_type='WebUser',
            batch_id=self.batch.id,
            domain_memberships=[
                {'domain': 'test1', 'is_admin': True},
            ]
        )
        DomainMembershipDim.commit(self.batch)
        # should create 3 domain membership columns instead of 4
        self.assertEqual(
            DomainMembershipDim.objects.count(), 3
        )
        # u3 user should have only 1 domain-membership
        dim_id_of_user3 = UserDim.objects.filter(user_id='u3')[0].id
        self.assertEqual(
            DomainMembershipDim.objects.filter(user_dim_id=dim_id_of_user3).count(),
            1
        )


class TestUserGroupDim(BaseWarehouseTestCase):

    domain = 'user-group-dim-test'
    slug = 'user_group_dim'

    @classmethod
    def setUpClass(cls):
        super(TestUserGroupDim, cls).setUpClass()
        cls.batch = create_batch(cls.slug)
        cls.blue_dog = create_user_staging_record(cls.domain,
                                                  username='blue-dog',
                                                  batch_id=cls.batch.id)
        cls.black_dog = create_user_staging_record(cls.domain,
                                                   username='black-dog',
                                                   batch_id=cls.batch.id)
        cls.yellow_cat = create_user_staging_record(cls.domain,
                                                    username='yellow-cat',
                                                    batch_id=cls.batch.id)

    @classmethod
    def tearDownClass(cls):
        GroupStagingTable.clear_records()
        UserStagingTable.clear_records()
        GroupDim.clear_records()
        UserDim.clear_records()
        UserGroupDim.clear_records()
        super(TestUserGroupDim, cls).tearDownClass()

    def test_basic_user_group_insert(self):
        UserDim.commit(self.batch)
        self.assertEqual(UserDim.objects.count(), 3)

        # Setup group records to have multiple users
        dogs = create_group_staging_record(
            self.domain,
            'dogs',
            user_ids=[self.blue_dog.user_id, self.black_dog.user_id],
            batch_id=self.batch.id
        )
        create_group_staging_record(
            self.domain,
            'cats',
            user_ids=[self.yellow_cat.user_id],
            batch_id=self.batch.id
        )
        GroupDim.commit(self.batch)
        self.assertEqual(GroupDim.objects.count(), 2)

        UserGroupDim.commit(self.batch)
        self.assertEqual(UserGroupDim.objects.count(), 3)
        dog_relations = UserGroupDim.objects.filter(group_dim=GroupDim.objects.get(group_id=dogs.group_id))
        self.assertEqual(
            dog_relations.count(),
            2,
        )
        self.assertEqual(
            set(dog_relations.values_list('user_dim_id', flat=True)),
            set(UserDim.objects.filter(
                user_id__in=[self.blue_dog.user_id, self.black_dog.user_id]
            ).values_list('id', flat=True)),
        )


class TestLocationDim(BaseWarehouseTestCase):

    domain = 'location-dim-test'
    slug = 'location_dim'

    @classmethod
    def setUpClass(cls):
        super(TestLocationDim, cls).setUpClass()
        cls.batch = create_batch(cls.slug)

    def tearDown(self):
        LocationStagingTable.clear_records()
        LocationDim.clear_records()
        super(TestLocationDim, self).tearDown()

    def test_location_dim(self):
        tree = {
            ('Illinois', 'state'): {
                ('Naperville', 'city'): {
                    ('Home', 'home'): {}
                },
                ('Chicago', 'city'): {},
            }
        }
        create_location_records_from_tree(self.domain, tree, self.batch.id)

        self.assertEqual(LocationStagingTable.objects.count(), 4)

        LocationDim.commit(self.batch)
        self.assertEqual(LocationDim.objects.count(), 4)
        home_location = LocationDim.objects.filter(name='Home').first()

        self.assertEqual(
            home_location.location_level_0,
            LocationDim.objects.filter(name='Illinois').first().sql_location_id,
        )
        self.assertEqual(
            home_location.location_level_1,
            LocationDim.objects.filter(name='Naperville').first().sql_location_id,
        )
        self.assertEqual(home_location.location_level_2, home_location.sql_location_id)
        self.assertEqual(home_location.location_level_3, None)
        self.assertEqual(home_location.location_level_4, None)
        self.assertEqual(home_location.location_level_5, None)
        self.assertEqual(home_location.location_level_6, None)
        self.assertEqual(home_location.location_level_7, None)

        self.assertEqual(home_location.level, 2)
        self.assertEqual(home_location.location_type_name, 'home')
        self.assertEqual(home_location.location_type_code, 'home')

        root_location = LocationDim.objects.filter(name='Illinois').first()
        self.assertEqual(root_location.location_level_0, root_location.sql_location_id)
        self.assertEqual(root_location.level, 0)

    def test_location_dim_update(self):
        tree = {
            ('Illinois', 'state'): {
                ('Naperville', 'city'): {
                    ('Home', 'home'): {}
                },
                ('Chicago', 'city'): {},
            }
        }
        create_location_records_from_tree(self.domain, tree, self.batch.id)
        LocationDim.commit(self.batch)
        self.assertEqual(LocationDim.objects.count(), 4)

        # Let's add one more location under Naperville to ensure that the dim updates
        # when it's not a root node
        LocationStagingTable.clear_records()
        home_location = LocationDim.objects.filter(name='Home').first()
        city_location = LocationDim.objects.filter(name='Naperville').first()
        create_location_staging_record(
            self.domain,
            'Other home',
            sql_location_id=10,
            # Give it the same parent as the Home location
            sql_parent_location_id=city_location.sql_location_id,
            location_type_id=home_location.location_type_id,
            batch_id=self.batch.id
        )

        LocationDim.commit(self.batch)
        self.assertEqual(LocationDim.objects.count(), 5)


class TestAppDim(BaseWarehouseTestCase):

    domain = 'app-dim-test'
    slug = 'app_dim'

    @classmethod
    def setUpClass(cls):
        super(TestAppDim, cls).setUpClass()
        cls.batch = create_batch(cls.slug)

    @classmethod
    def tearDownClass(cls):
        ApplicationDim.clear_records()
        ApplicationStagingTable.clear_records()
        super(TestAppDim, cls).tearDownClass()

    def test_app_dim(self):
        create_application_staging_record(self.domain, 'test-app', batch_id=self.batch.id)
        create_application_staging_record(self.domain, 'test-deleted', doc_type='Application-Deleted', batch_id=self.batch.id)
        ApplicationDim.commit(self.batch)
        self.assertEqual(ApplicationDim.objects.count(), 2)
        test_app = ApplicationDim.objects.get(name='test-app')
        self.assertEqual(test_app.deleted, False)
        deleted_app = ApplicationDim.objects.get(name='test-deleted')
        self.assertEqual(deleted_app.deleted, True)
