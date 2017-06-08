from datetime import datetime, timedelta
from django.test import TestCase

from corehq.apps.domain.models import Domain
from corehq.apps.groups.models import Group
from corehq.apps.users.models import CommCareUser, WebUser
from corehq.apps.users.dbaccessors.all_commcare_users import (
    delete_all_users,
    hard_delete_deleted_users,
)

from corehq.warehouse.dbaccessors import (
    get_group_ids_by_last_modified,
    get_user_ids_by_last_modified,
)


class TestDbAccessors(TestCase):
    domain = 'warehouse'

    @classmethod
    def setUpClass(cls):
        # Needed because other tests do not always clean up their users.
        delete_all_users()
        hard_delete_deleted_users()

        cls.g1 = Group(domain=cls.domain, name='group')
        cls.g1.save()

        cls.g2 = Group(domain=cls.domain, name='group')
        cls.g2.soft_delete()

        cls.domain_obj = Domain(
            name=cls.domain,
            is_active=True,
        )
        cls.domain_obj.save()

        cls.web_user = WebUser.create(cls.domain, 'web-user', '***')
        cls.commcare_user = CommCareUser.create(cls.domain, 'cc-user', '***')
        cls.commcare_user.retire()

    @classmethod
    def tearDownClass(cls):
        cls.g1.delete()
        cls.g2.delete()
        cls.domain_obj.delete()

    def test_get_group_ids_by_last_modified(self):
        start = datetime.utcnow() - timedelta(days=3)
        end = datetime.utcnow() + timedelta(days=3)

        self.assertEqual(
            set(get_group_ids_by_last_modified(start, end)),
            set([self.g1._id, self.g2._id]),
        )

        self.assertEqual(
            set(get_group_ids_by_last_modified(start, end - timedelta(days=4))),
            set(),
        )

    def test_get_user_ids_by_last_modified(self):
        start = datetime.utcnow() - timedelta(days=3)
        end = datetime.utcnow() + timedelta(days=3)

        self.assertEqual(
            set(get_user_ids_by_last_modified(start, end)),
            set([self.web_user._id, self.commcare_user._id]),
        )

        self.assertEqual(
            set(get_user_ids_by_last_modified(start, end - timedelta(days=4))),
            set(),
        )
