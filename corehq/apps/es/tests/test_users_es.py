from django.test import TestCase

from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.es.tests.utils import es_test
from corehq.apps.es.users import (
    UserES,
    _empty_user_data_property,
    missing_or_empty_user_data_property,
    _missing_user_data_property,
    user_adapter,
)
from corehq.apps.users.models import CommCareUser


@es_test(requires=[user_adapter], setup_class=True)
class TestUserDataFilters(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.domain = 'user-data-es-test'
        cls.domain_obj = create_domain(cls.domain)
        cls.addClassCleanup(cls.domain_obj.delete)

        cls.user_with_data = CommCareUser.create(
            username="user1",
            domain=cls.domain,
            password="***********",
            created_by=None,
            created_via=None,
            user_data={'location': 'Boston'}
        )
        cls.user_empty_data = CommCareUser.create(
            username="user2",
            domain=cls.domain,
            password="***********",
            created_by=None,
            created_via=None,
            user_data={'location': ''}
        )
        cls.user_no_data = CommCareUser.create(
            username="user3",
            domain=cls.domain,
            password="***********",
            created_by=None,
            created_via=None
        )
        cls.user_other_data = CommCareUser.create(
            username="user4",
            domain=cls.domain,
            password="***********",
            created_by=None,
            created_via=None,
            user_data={'other_prop': 'value'}
        )

        for user in [cls.user_with_data, cls.user_empty_data, cls.user_no_data, cls.user_other_data]:
            user_adapter.index(user, refresh=True)
            cls.addClassCleanup(user.delete, None, None)

    def test_missing_or_empty_user_data_property(self):
        results = (UserES()
                   .domain(self.domain)
                   .filter(missing_or_empty_user_data_property('location'))
                   .get_ids())

        expected_ids = [self.user_no_data.user_id, self.user_empty_data.user_id, self.user_other_data.user_id]
        self.assertCountEqual(results, expected_ids)

    def test_missing_or_empty_user_data_multiple_properties(self):
        results = (UserES()
                   .domain(self.domain)
                   .filter(missing_or_empty_user_data_property('location'))
                   .filter(missing_or_empty_user_data_property('other_prop'))
                   .get_ids())

        expected_ids = [self.user_no_data.user_id, self.user_empty_data.user_id]
        self.assertCountEqual(results, expected_ids)

    def test_missing_user_data_property(self):
        results = (UserES()
                   .domain(self.domain)
                   .filter(_missing_user_data_property('location'))
                   .get_ids())

        expected_ids = [self.user_no_data.user_id, self.user_other_data.user_id]
        self.assertCountEqual(results, expected_ids)

    def test_empty_user_data_property(self):
        results = (UserES()
                   .domain(self.domain)
                   .filter(_empty_user_data_property('location'))
                   .get_ids())

        expected_ids = [self.user_empty_data.user_id]
        self.assertCountEqual(results, expected_ids)
