from corehq.apps.change_feed import topics
from corehq.apps.change_feed.topics import get_topic_offset
from corehq.apps.change_feed.producer import producer
from corehq.apps.es.client import manager
from corehq.apps.es.groups import group_adapter
from corehq.apps.es.tests.utils import (
    es_test,
)
from corehq.apps.es.users import user_adapter
from corehq.apps.groups.models import Group
from corehq.apps.locations.tests.util import LocationHierarchyTestCase
from corehq.apps.reports.models import HQUserType
from corehq.apps.reports.standard.cases.utils import get_case_owners
from corehq.apps.users.models import WebUser, CommCareUser
from corehq.form_processor.change_publishers import change_meta_from_sql_form
from corehq.form_processor.interfaces.processor import FormProcessorInterface
from corehq.form_processor.tests.utils import FormProcessorTestUtils
from corehq.form_processor.utils import TestFormMetadata
from corehq.pillows.xform import get_xform_pillow
from corehq.util.test_utils import get_form_ready_to_save


class BaseCaseOwnersTest(LocationHierarchyTestCase):
    location_type_names = ['state', 'county', 'city']
    location_structure = [
        ('Massachusetts', [
            ('Middlesex', [
                ('Cambridge', []),
                ('Somerville', []),
            ]),
            ('Suffolk', [
                ('Boston', []),
                ('Revere', []),
            ])
        ]),
        ('New York', [
            ('New York City', [
                ('Manhattan', []),
                ('Brooklyn', []),
                ('Queens', []),
            ]),
        ]),
    ]

    @classmethod
    def _set_up_unknown_admin_users(cls):
        cls.admin_user_id = 'test-admin-user'
        cls.unknown_user_id = 'test-unknown-user'
        for username, user_id in (
            ('unknown', cls.unknown_user_id),
            ('admin', cls.admin_user_id),
        ):
            metadata = TestFormMetadata(domain=cls.domain, user_id=user_id, username=username)
            form = get_form_ready_to_save(metadata)
            FormProcessorInterface(domain=cls.domain).save_processed_models([form])
            topic = topics.FORM_SQL
            since = get_topic_offset(topics.FORM_SQL)
            producer.send_change(topic, change_meta_from_sql_form(form))
            pillow = get_xform_pillow()
            pillow.process_changes(since=since, forever=False)

    @classmethod
    def _set_up_commcare_users(cls):
        cls.users = []
        for index in range(6):
            user = CommCareUser.create(
                cls.domain, f'user-test-{index}', 'Passw0rd!', None, None
            )
            if index < 2:
                user.set_location(cls.locations['Massachusetts'])
                user.add_to_assigned_locations(cls.locations['Suffolk'])
                user.save()
            elif 2 <= index < 4:
                user.set_location(cls.locations['Middlesex'])
                user.add_to_assigned_locations(cls.locations['Cambridge'])
                user.save()
            elif 4 <= index:
                user.set_location(cls.locations['New York'])
                user.add_to_assigned_locations(cls.locations['Brooklyn'])
                user.add_to_assigned_locations(cls.locations['Queens'])
                user.save()
            user_adapter.index(user)
            cls.users.append(user)

    @classmethod
    def _set_up_web_users(cls):
        cls.web_users = []
        for index in range(2):
            web_user = WebUser.create(
                cls.domain, f'tester-{index}@iloveplants.org', 'Passw0rd!', None, None
            )
            user_adapter.index(web_user)
            cls.web_users.append(web_user)

    @classmethod
    def _set_up_groups(cls):
        cls.group1 = Group(
            name='test-group1',
            domain=cls.domain,
            users=[cls.users[1]._id, cls.users[3]._id, cls.users[5]._id],
        )
        cls.group1.save()
        group_adapter.index(cls.group1)

        cls.group2 = Group(
            name='test-group2',
            domain=cls.domain,
            case_sharing=True,
            users=[cls.users[0]._id, cls.users[2]._id, cls.users[4]._id],
        )
        cls.group2.save()
        group_adapter.index(cls.group2)

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.location_types['state'].view_descendants = True
        cls.location_types['state'].save()
        cls.location_types['city'].shares_cases = True
        cls.location_types['city'].save()

        cls._set_up_unknown_admin_users()
        cls._set_up_commcare_users()
        cls._set_up_web_users()
        cls._set_up_groups()

        manager.index_refresh(user_adapter.index_name)
        manager.index_refresh(group_adapter.index_name)

    @classmethod
    def tearDownClass(cls):
        FormProcessorTestUtils.delete_all_xforms()

        for group in [cls.group1, cls.group2]:
            group.delete()

        for user in cls.users + cls.web_users:
            from couchdbkit import ResourceNotFound
            try:
                user.delete(cls.domain, None)
            except ResourceNotFound:
                pass

        super().tearDownClass()


@es_test(requires=[user_adapter, group_adapter], setup_class=True)
class CaseOwnersTest(BaseCaseOwnersTest):
    domain = 'get-case-owners-test'

    def test_web_users(self):
        owners = get_case_owners(True, self.domain, [f't__{HQUserType.WEB}'])
        web_user_ids = [u._id for u in self.web_users]
        self.assertListEqual(sorted(owners), sorted(web_user_ids))

    def test_web_users_restricted(self):
        owners = get_case_owners(False, self.domain, [f't__{HQUserType.WEB}'])
        self.assertListEqual(owners, [])

    def test_admin_users(self):
        owners = get_case_owners(True, self.domain, [f't__{HQUserType.ADMIN}'])
        self.assertListEqual(owners, [self.admin_user_id])

    def test_admin_users_restricted(self):
        owners = get_case_owners(False, self.domain, [f't__{HQUserType.ADMIN}'])
        self.assertListEqual(owners, [])

    def test_unknown_users(self):
        owners = get_case_owners(True, self.domain, [f't__{HQUserType.UNKNOWN}'])
        self.assertListEqual(owners, [self.unknown_user_id])

    def test_unknown_users_restricted(self):
        owners = get_case_owners(False, self.domain, [f't__{HQUserType.UNKNOWN}'])
        self.assertListEqual(owners, [])

    def test_deactivated_users(self):
        owners = get_case_owners(True, self.domain, [f't__{HQUserType.DEACTIVATED}'])
        self.assertListEqual(owners, [])

    def test_deactivated_users_restricted(self):
        owners = get_case_owners(False, self.domain, [f't__{HQUserType.DEACTIVATED}'])
        self.assertListEqual(owners, [])

    def test_demo_users(self):
        owners = get_case_owners(True, self.domain, [f't__{HQUserType.DEMO_USER}'])
        expected_owners = [
            'demo_user',
            'demo_user_group_id',
        ]
        self.assertListEqual(sorted(owners), sorted(expected_owners))

    def test_demo_users_restricted(self):
        owners = get_case_owners(False, self.domain, [f't__{HQUserType.DEMO_USER}'])
        self.assertListEqual(owners, [])

    def test_reporting_groups(self):
        owners = get_case_owners(True, self.domain, [f'g__{self.group1._id}'])
        expected_owners = [
            self.users[1]._id,
            self.users[3]._id,
            self.users[5]._id,
        ]
        self.assertListEqual(sorted(owners), sorted(expected_owners))

    def test_reporting_groups_restricted(self):
        owners = get_case_owners(False, self.domain, [f'g__{self.group1._id}'])
        self.assertListEqual(owners, [])

    def test_case_sharing_groups(self):
        owners = get_case_owners(True, self.domain, [f'g__{self.group2._id}'])
        expected_owners = [
            self.group2._id,
            self.users[0]._id,
            self.users[2]._id,
            self.users[4]._id,
        ]
        self.assertListEqual(sorted(owners), sorted(expected_owners))

    def test_case_sharing_groups_restricted(self):
        owners = get_case_owners(False, self.domain, [f'g__{self.group2._id}'])
        self.assertListEqual(owners, [])

    def test_location_case_sharing(self):
        location_id = self.locations['Brooklyn'].location_id
        owners = get_case_owners(True, self.domain, [f'l__{location_id}'])
        expected_owners = [
            location_id,
            self.users[4]._id,
            self.users[5]._id,
        ]
        self.assertListEqual(sorted(owners), sorted(expected_owners))

    def test_location_case_sharing_restricted(self):
        location_id = self.locations['Brooklyn'].location_id
        owners = get_case_owners(False, self.domain, [f'l__{location_id}'])
        expected_owners = [
            location_id,
            self.users[4]._id,
            self.users[5]._id,
        ]
        self.assertListEqual(sorted(owners), sorted(expected_owners))

    def test_location_case_sharing_other_users(self):
        location_id = self.locations['Brooklyn'].location_id
        outside_user_id = self.users[2]._id
        owners = get_case_owners(True, self.domain, [
            f'l__{location_id}', f'u__{outside_user_id}'
        ])
        expected_owners = [
            location_id,
            self.locations['Middlesex'].location_id,
            self.locations['Cambridge'].location_id,
            self.locations['Somerville'].location_id,
            self.users[2]._id,
            self.users[4]._id,
            self.users[5]._id,
            self.group2._id,
        ]
        self.assertListEqual(sorted(owners), sorted(expected_owners))

    def test_location_case_sharing_other_users_restricted(self):
        location_id = self.locations['Brooklyn'].location_id
        outside_user_id = self.users[2]._id
        owners = get_case_owners(False, self.domain, [
            f'l__{location_id}', f'u__{outside_user_id}'
        ])
        expected_owners = [
            location_id,
            self.locations['Middlesex'].location_id,
            self.locations['Cambridge'].location_id,
            self.locations['Somerville'].location_id,
            self.users[2]._id,
            self.users[4]._id,
            self.users[5]._id,
            self.group2._id,
        ]
        self.assertListEqual(sorted(owners), sorted(expected_owners))

    def test_location_descendants(self):
        location_id = self.locations['New York'].location_id
        owners = get_case_owners(True, self.domain, [f'l__{location_id}'])
        expected_owners = [
            location_id,
            self.locations['New York City'].location_id,
            self.locations['Manhattan'].location_id,
            self.locations['Brooklyn'].location_id,
            self.locations['Queens'].location_id,
            self.users[4]._id,
            self.users[5]._id,
        ]
        self.assertListEqual(sorted(owners), sorted(expected_owners))

    def test_location_descendants_restricted(self):
        location_id = self.locations['New York'].location_id
        owners = get_case_owners(False, self.domain, [f'l__{location_id}'])
        expected_owners = [
            location_id,
            self.locations['New York City'].location_id,
            self.locations['Manhattan'].location_id,
            self.locations['Brooklyn'].location_id,
            self.locations['Queens'].location_id,
            self.users[4]._id,
            self.users[5]._id,
        ]
        self.assertListEqual(sorted(owners), sorted(expected_owners))

    def test_selected_user_ids(self):
        selected_users = [
            self.users[2],
            self.users[0],
        ]
        owners = get_case_owners(
            True, self.domain, [f'u__{u._id}' for u in selected_users]
        )
        expected_owners = [
            self.locations['Massachusetts'].location_id,
            self.locations['Middlesex'].location_id,
            self.locations['Cambridge'].location_id,
            self.locations['Somerville'].location_id,
            self.locations['Suffolk'].location_id,
            self.locations['Boston'].location_id,
            self.locations['Revere'].location_id,
            self.users[0]._id,
            self.users[2]._id,
            self.group2._id,
        ]
        self.assertListEqual(sorted(owners), sorted(expected_owners))

    def test_selected_user_ids_restricted(self):
        selected_users = [
            self.users[2],
            self.users[0],
        ]
        owners = get_case_owners(
            False, self.domain, [f'u__{u._id}' for u in selected_users]
        )
        expected_owners = [
            self.locations['Massachusetts'].location_id,
            self.locations['Middlesex'].location_id,
            self.locations['Cambridge'].location_id,
            self.locations['Somerville'].location_id,
            self.locations['Suffolk'].location_id,
            self.locations['Boston'].location_id,
            self.locations['Revere'].location_id,
            self.users[0]._id,
            self.users[2]._id,
            self.group2._id,
        ]
        self.assertListEqual(sorted(owners), sorted(expected_owners))

    def test_selected_web_user_ids(self):
        selected_users = [
            self.web_users[0],
        ]
        owners = get_case_owners(
            True, self.domain, [f'u__{u._id}' for u in selected_users]
        )
        expected_owners = [
            self.web_users[0]._id,
        ]
        self.assertListEqual(sorted(owners), sorted(expected_owners))

    def test_selected_web_user_ids_restricted(self):
        selected_users = [
            self.web_users[0],
        ]
        owners = get_case_owners(
            False, self.domain, [f'u__{u._id}' for u in selected_users]
        )
        expected_owners = [
            self.web_users[0]._id,
        ]
        self.assertListEqual(sorted(owners), sorted(expected_owners))
