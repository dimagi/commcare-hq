from django.core.exceptions import ValidationError
from django.test import TestCase

import pytest

from corehq.apps.app_manager.const import USERCASE_TYPE
from corehq.apps.es.case_search import case_search_adapter
from corehq.apps.es.tests.utils import es_test
from corehq.apps.integration.kyc.models import KycConfig, UserDataStore, KycUser
from corehq.apps.users.models import CommCareUser
from corehq.form_processor.models import CommCareCase
from corehq.form_processor.tests.utils import create_case
from corehq.motech.const import OAUTH2_CLIENT
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
        # Doesn't save ConnectionSettings
        assert ConnectionSettings.objects.count() == 0

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

    def test_existing_connection_settings(self):
        connx = ConnectionSettings.objects.create(
            domain=DOMAIN,
            name='custom connection',
            url='https://example.com',
            auth_type=OAUTH2_CLIENT,
            client_id='client_id',
            client_secret='client_secret',
            token_url='token_url',
        )
        config = KycConfig(
            domain=DOMAIN,
            user_data_store=UserDataStore.USER_CASE,
            connection_settings=connx,
        )
        assert config.get_connection_settings() == connx


class BaseKycUsersSetup(TestCase):
    def setUp(self):
        super().setUp()
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
        self.other_case = create_case(
            DOMAIN,
            case_type='other_case_type',
            save=True,
            case_json={'other_case_property': 'other_case_value'},
        )
        self.addCleanup(
            CommCareCase.objects.hard_delete_cases,
            DOMAIN,
            [self.user_case.case_id, self.other_case.case_id]
        )


class TestGetUserObjectsUsers(BaseKycUsersSetup):

    def test_custom_user_data(self):
        config = KycConfig(
            domain=DOMAIN,
            user_data_store=UserDataStore.CUSTOM_USER_DATA,
        )
        kyc_users = config.get_kyc_users()
        assert len(kyc_users) == 1
        assert kyc_users[0].user_data == {
            'commcare_profile': '',
            'custom_field': 'custom_value',
        }

    def test_custom_user_data_by_ids(self):
        config = KycConfig(
            domain=DOMAIN,
            user_data_store=UserDataStore.CUSTOM_USER_DATA,
        )
        selected_ids = [self.commcare_user.user_id]
        kyc_users = config.get_kyc_users_by_ids(selected_ids)
        assert len(kyc_users) == 1
        assert kyc_users[0].user_data == {
            'commcare_profile': '',
            'custom_field': 'custom_value',
        }

    def test_user_case(self):
        config = KycConfig(
            domain=DOMAIN,
            user_data_store=UserDataStore.USER_CASE,
        )
        kyc_users = config.get_kyc_users()
        assert len(kyc_users) == 1
        assert kyc_users[0].user_data == {
            'user_case_property': 'user_case_value',
        }

    def test_user_case_by_ids(self):
        config = KycConfig(
            domain=DOMAIN,
            user_data_store=UserDataStore.USER_CASE,
        )
        selected_ids = [self.commcare_user.user_id]
        kyc_users = config.get_kyc_users_by_ids(selected_ids)
        assert len(kyc_users) == 1
        assert kyc_users[0].user_data == {
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
        self.addCleanup(
            CommCareCase.objects.hard_delete_cases,
            DOMAIN,
            [self.other_case.case_id]
        )

    def test_other_case_type(self):
        config = KycConfig(
            domain=DOMAIN,
            user_data_store=UserDataStore.OTHER_CASE_TYPE,
            other_case_type='other_case_type',
        )
        kyc_users = config.get_kyc_users()
        assert len(kyc_users) == 1
        assert kyc_users[0].user_data == {
            'other_case_property': 'other_case_value',
        }

    def test_other_case_type_by_ids(self):
        config = KycConfig(
            domain=DOMAIN,
            user_data_store=UserDataStore.OTHER_CASE_TYPE,
            other_case_type='other_case_type',
        )
        selected_ids = [self.other_case.case_id]
        kyc_users = config.get_kyc_users_by_ids(selected_ids)
        assert len(kyc_users) == 1
        assert kyc_users[0].user_data == {
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
            config.get_kyc_users()


class TestKycUser(BaseKycUsersSetup):

    def test_custom_user_data(self):
        config = KycConfig(
            domain=DOMAIN,
            user_data_store=UserDataStore.CUSTOM_USER_DATA,
        )

        kyc_user = KycUser(config, self.commcare_user)

        assert kyc_user.user_data == {
            'custom_field': 'custom_value',
            'commcare_profile': '',
        }
        assert kyc_user.user_id == self.commcare_user.user_id

    def test_user_case(self):
        config = KycConfig(
            domain=DOMAIN,
            user_data_store=UserDataStore.USER_CASE,
        )

        kyc_user = KycUser(config, self.commcare_user)

        assert kyc_user.user_data == {'user_case_property': 'user_case_value'}
        assert kyc_user.user_id == self.commcare_user.user_id

    def test_other_case_type(self):
        config = KycConfig(
            domain=DOMAIN,
            user_data_store=UserDataStore.OTHER_CASE_TYPE,
            other_case_type='other_case_type',
        )

        kyc_user = KycUser(config, self.other_case)

        assert kyc_user.user_data == {'other_case_property': 'other_case_value'}
        assert kyc_user.user_id == self.other_case.case_id

    def test_kyc_verification_initial_values(self):
        config = KycConfig(
            domain=DOMAIN,
            user_data_store=UserDataStore.CUSTOM_USER_DATA,
        )

        kyc_user = KycUser(config, self.commcare_user)

        assert kyc_user.kyc_is_verified is None
        assert kyc_user.kyc_last_verified_at is None
        assert kyc_user.kyc_provider is None

    def _assert_for_verification_status(self, kyc_user, expected_status, expected_provider):
        assert kyc_user.kyc_is_verified is expected_status
        assert kyc_user.kyc_last_verified_at is not None
        assert kyc_user.kyc_provider == expected_provider

    def test_update_verification_status_for_custom_user_data(self):
        config = KycConfig(
            domain=DOMAIN,
            user_data_store=UserDataStore.CUSTOM_USER_DATA,
        )

        kyc_user = KycUser(config, self.commcare_user)
        kyc_user.update_verification_status(True)

        self._assert_for_verification_status(kyc_user, True, config.provider)

    def test_update_verification_status_for_user_case(self):
        config = KycConfig(
            domain=DOMAIN,
            user_data_store=UserDataStore.USER_CASE,
        )

        kyc_user = KycUser(config, self.commcare_user)
        kyc_user.update_verification_status(True)

        self._assert_for_verification_status(kyc_user, True, config.provider)

    def test_update_verification_status_for_other_case_type(self):
        config = KycConfig(
            domain=DOMAIN,
            user_data_store=UserDataStore.OTHER_CASE_TYPE,
        )

        kyc_user = KycUser(config, self.other_case)
        kyc_user.update_verification_status(True)

        self._assert_for_verification_status(kyc_user, True, config.provider)
