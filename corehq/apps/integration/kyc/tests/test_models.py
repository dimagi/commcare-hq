from django.core.exceptions import ValidationError
from django.test import TestCase

import pytest

from corehq.apps.app_manager.const import USERCASE_TYPE
from corehq.apps.es.case_search import case_search_adapter
from corehq.apps.es.tests.utils import es_test
from corehq.apps.integration.kyc.models import KycConfig, UserDataStore
from corehq.apps.users.models import CommCareUser
from corehq.form_processor.tests.utils import create_case
from corehq.motech.models import ConnectionSettings

DOMAIN = 'test-domain'


class TestGetConnectionSettings(TestCase):

    def test_valid_without_connection_settings(self):
        config = KycConfig(
            domain=DOMAIN,
            user_data_store=UserDataStore.USER_CASE,
        )
        # Does not raise `django.db.utils.IntegrityError`
        config.save()

    def test_get_connection_settings(self):
        config = KycConfig(
            domain=DOMAIN,
            user_data_store=UserDataStore.USER_CASE,
        )
        assert ConnectionSettings.objects.count() == 0

        connx = config.get_connection_settings()
        assert isinstance(connx, ConnectionSettings)
        # First call creates ConnectionSettings
        assert ConnectionSettings.objects.count() == 1

        connx = config.get_connection_settings()
        assert isinstance(connx, ConnectionSettings)
        # Subsequent calls get existing ConnectionSettings
        assert ConnectionSettings.objects.count() == 1

    def test_bad_config(self):
        config = KycConfig(
            domain=DOMAIN,
            user_data_store=UserDataStore.USER_CASE,
            provider='invalid',
        )
        with pytest.raises(
            ValueError,
            match="^Unable to determine connection settings for KYC provider "
                  "'invalid'.$",
        ):
            config.get_connection_settings()


class TestGetUserObjectsUsers(TestCase):

    def setUp(self):
        self.commcare_user = CommCareUser.create(
            DOMAIN, f'test.user@{DOMAIN}.commcarehq.org', 'Passw0rd!',
            None, None,
            user_data={'custom_field': 'custom_value'},
        )
        self.addCleanup(self.commcare_user.delete, DOMAIN, deleted_by=None)
        self.user_case = create_case(
            DOMAIN,
            case_type=USERCASE_TYPE,
            user_id=self.commcare_user._id,
            name='test.user',
            external_id=self.commcare_user._id,
            save=True,
            case_json={'user_case_property': 'user_case_value'},
        )

    def test_custom_user_data(self):
        config = KycConfig(
            domain=DOMAIN,
            user_data_store=UserDataStore.CUSTOM_USER_DATA,
        )
        commcare_users = config.get_user_objects()
        assert len(commcare_users) == 1
        user_data = commcare_users[0].get_user_data(DOMAIN).to_dict()
        assert user_data == {
            'commcare_profile': '',
            'custom_field': 'custom_value',
        }

    def test_user_case(self):
        config = KycConfig(
            domain=DOMAIN,
            user_data_store=UserDataStore.USER_CASE,
        )
        commcare_users = config.get_user_objects()
        assert len(commcare_users) == 1
        user_case = commcare_users[0].get_usercase()
        assert user_case.case_json == {
            'user_case_property': 'user_case_value',
        }


@es_test(requires=[case_search_adapter])
class TestGetUserObjectsCases(TestCase):

    def setUp(self):
        self.other_case = create_case(
            DOMAIN,
            case_type='other_case_type',
            save=True,
            case_json={'other_case_property': 'other_case_value'},
        )
        case_search_adapter.bulk_index([self.other_case], refresh=True)

    def test_other_case_type(self):
        config = KycConfig(
            domain=DOMAIN,
            user_data_store=UserDataStore.OTHER_CASE_TYPE,
            other_case_type='other_case_type',
        )
        commcare_cases = config.get_user_objects()
        assert len(commcare_cases) == 1
        assert commcare_cases[0].case_json == {
            'other_case_property': 'other_case_value',
        }

    def test_other_case_type_clean(self):
        config = KycConfig(
            domain=DOMAIN,
            user_data_store=UserDataStore.OTHER_CASE_TYPE,
        )
        with pytest.raises(ValidationError):
            config.clean()

    def test_assert_other_case_type(self):
        config = KycConfig(
            domain=DOMAIN,
            user_data_store=UserDataStore.OTHER_CASE_TYPE,
        )
        with pytest.raises(AssertionError):
            config.get_user_objects()
