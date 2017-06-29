from datetime import datetime, timedelta
from django.test import TestCase

from corehq.apps.users.util import SYSTEM_USER_ID, DEMO_USER_ID
from corehq.apps.commtrack.const import COMMTRACK_USERNAME
from corehq.pillows.utils import (
    SYSTEM_USER_TYPE,
    DEMO_USER_TYPE,
    COMMCARE_SUPPLY_USER_TYPE,
    WEB_USER_TYPE,
    MOBILE_USER_TYPE,
)
from corehq.warehouse.tests.utils import (
    create_user_staging_record,
    create_location_records_from_tree,
    create_location_staging_record,
    create_group_staging_record,
)
from corehq.warehouse.models import (
    UserStagingTable,
    UserDim,
    GroupStagingTable,
    GroupDim,
    UserGroupDim,
    LocationDim,
    LocationStagingTable,
    LocationTypeStagingTable,
)


class TestUserDim(TestCase):

    domain = 'user-dim-test'

    @classmethod
    def setUpClass(cls):
        super(TestUserDim, cls).setUpClass()
        cls.records = [
            create_user_staging_record(
                cls.domain,
                user_id=SYSTEM_USER_ID,
                username='system_bob',
            ),
            create_user_staging_record(
                cls.domain,
                user_id=DEMO_USER_ID,
                username='demo_sally',
            ),
            create_user_staging_record(
                cls.domain,
                user_id=COMMTRACK_USERNAME,
                username='commtrack_billy',
            ),
            create_user_staging_record(
                cls.domain,
                user_id='beeboobop',
                username='web',
                doc_type='WebUser'
            ),
            create_user_staging_record(
                cls.domain,
                user_id='greengoblin',
                username='mobile',
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
        start = datetime.utcnow() - timedelta(days=3)
        end = datetime.utcnow() + timedelta(days=3)

        UserDim.commit(start, end)

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


class TestUserGroupDim(TestCase):

    domain = 'user-group-dim-test'

    @classmethod
    def setUpClass(cls):
        super(TestUserGroupDim, cls).setUpClass()
        cls.blue_dog = create_user_staging_record(cls.domain, username='blue-dog')
        cls.black_dog = create_user_staging_record(cls.domain, username='black-dog')
        cls.yellow_cat = create_user_staging_record(cls.domain, username='yellow-cat')

    @classmethod
    def tearDownClass(cls):
        GroupStagingTable.clear_records()
        UserStagingTable.clear_records()
        GroupDim.clear_records()
        UserDim.clear_records()
        UserGroupDim.clear_records()
        super(TestUserGroupDim, cls).tearDownClass()

    def test_basic_user_group_insert(self):
        start = datetime.utcnow() - timedelta(days=3)
        end = datetime.utcnow() + timedelta(days=3)

        UserDim.commit(start, end)
        self.assertEqual(UserDim.objects.count(), 3)

        # Setup group records to have multiple users
        dogs = create_group_staging_record(
            self.domain,
            'dogs',
            user_ids=[self.blue_dog.user_id, self.black_dog.user_id],
        )
        create_group_staging_record(
            self.domain,
            'cats',
            user_ids=[self.yellow_cat.user_id],
        )
        GroupDim.commit(start, end)
        self.assertEqual(GroupDim.objects.count(), 2)

        UserGroupDim.commit(start, end)
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

    def test_removed_users(self):
        '''
        This test ensures that we properly remove users when they are in
        the removed users field on the group.
        '''
        start = datetime.utcnow() - timedelta(days=3)
        end = datetime.utcnow() + timedelta(days=3)
        create_group_staging_record(
            self.domain,
            'dogs',
            user_ids=[self.blue_dog.user_id],
            removed_user_ids=[self.black_dog.user_id],
        )

        UserDim.commit(start, end)
        GroupDim.commit(start, end)
        UserGroupDim.commit(start, end)
        self.assertEqual(UserGroupDim.objects.count(), 2)
        self.assertEqual(UserGroupDim.objects.filter(deleted=True).count(), 1)


class TestLocationDim(TestCase):

    domain = 'location-dim-test'

    @classmethod
    def tearDownClass(cls):
        LocationStagingTable.clear_records()
        LocationTypeStagingTable.clear_records()
        LocationDim.clear_records()
        super(TestLocationDim, cls).tearDownClass()

    def test_location_dim(self):
        start = datetime.utcnow() - timedelta(days=3)
        end = datetime.utcnow() + timedelta(days=3)
        tree = {
            ('Illinois', 'state'): {
                ('Naperville', 'city'): {
                    ('Home', 'home'): {}
                },
                ('Chicago', 'city'): {},
            }
        }
        create_location_records_from_tree(self.domain, tree)

        self.assertEqual(LocationStagingTable.objects.count(), 4)
        self.assertEqual(LocationTypeStagingTable.objects.count(), 3)

        LocationDim.commit(start, end)
        self.assertEqual(LocationDim.objects.count(), 4)
        home_location = LocationDim.objects.filter(name='Home').first()

        self.assertEqual(
            home_location.location_level_2,
            LocationDim.objects.filter(name='Illinois').first().sql_location_id,
        )
        self.assertEqual(
            home_location.location_level_1,
            LocationDim.objects.filter(name='Naperville').first().sql_location_id,
        )
        self.assertEqual(home_location.location_level_0, home_location.sql_location_id)

        self.assertEqual(home_location.level, 2)
        self.assertEqual(home_location.location_type_name, 'home')
        self.assertEqual(home_location.location_type_code, 'home')

        root_location = LocationDim.objects.filter(name='Illinois').first()
        self.assertEqual(root_location.location_level_0, root_location.sql_location_id)
        self.assertEqual(root_location.level, 0)

    def test_location_dim_update(self):
        start = datetime.utcnow() - timedelta(days=3)
        end = datetime.utcnow() + timedelta(days=3)
        tree = {
            ('Illinois', 'state'): {
                ('Naperville', 'city'): {
                    ('Home', 'home'): {}
                },
                ('Chicago', 'city'): {},
            }
        }
        create_location_records_from_tree(self.domain, tree)
        LocationDim.commit(start, end)
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
        )

        LocationDim.commit(start, end)
        self.assertEqual(LocationDim.objects.count(), 5)
