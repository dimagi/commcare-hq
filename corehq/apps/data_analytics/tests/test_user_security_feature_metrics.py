from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from ..metric_registry import DomainContext
from ..feature_calcs import (
    calc_has_2fa_required,
    calc_has_organization,
    calc_has_shortened_timeout,
    calc_has_sso,
    calc_has_strong_passwords,
    calc_has_user_case_management,
    calc_mobile_user_groups,
    calc_user_profiles,
)


def _make_ctx(apps=None, **domain_attrs):
    domain_obj = MagicMock()
    domain_obj.name = 'test'
    domain_obj.full_applications.return_value = apps or []
    for k, v in domain_attrs.items():
        setattr(domain_obj, k, v)
    return DomainContext(domain_obj)


class TestCalcMobileUserGroups(SimpleTestCase):

    @patch('corehq.apps.groups.models.Group.by_domain')
    def test_counts_groups(self, mock_by_domain):
        mock_by_domain.return_value = [MagicMock(), MagicMock()]
        ctx = _make_ctx()
        assert calc_mobile_user_groups(ctx) == 2

    @patch('corehq.apps.groups.models.Group.by_domain')
    def test_zero_when_no_groups(self, mock_by_domain):
        mock_by_domain.return_value = []
        ctx = _make_ctx()
        assert calc_mobile_user_groups(ctx) == 0


class TestCalcHasUserCaseManagement(SimpleTestCase):

    @patch('corehq.apps.data_analytics.feature_calcs.actions_use_usercase')
    def test_true_when_usercase(self, mock_fn):
        mock_fn.return_value = True
        form = MagicMock()
        form.actions = MagicMock()
        module = MagicMock()
        module.get_forms.return_value = [form]
        app = MagicMock()
        app.is_remote_app.return_value = False
        app.get_modules.return_value = [module]
        ctx = _make_ctx(apps=[app])
        assert calc_has_user_case_management(ctx) is True

    @patch('corehq.apps.data_analytics.feature_calcs.actions_use_usercase')
    def test_false_when_no_usercase(self, mock_fn):
        mock_fn.return_value = False
        form = MagicMock()
        form.actions = MagicMock()
        module = MagicMock()
        module.get_forms.return_value = [form]
        app = MagicMock()
        app.is_remote_app.return_value = False
        app.get_modules.return_value = [module]
        ctx = _make_ctx(apps=[app])
        assert calc_has_user_case_management(ctx) is False

    def test_false_when_no_apps(self):
        ctx = _make_ctx(apps=[])
        assert calc_has_user_case_management(ctx) is False

    @patch('corehq.apps.app_manager.util.actions_use_usercase')
    def test_skips_forms_without_actions(self, mock_fn):
        form = MagicMock(spec=[])  # no 'actions' attribute
        module = MagicMock()
        module.get_forms.return_value = [form]
        app = MagicMock()
        app.is_remote_app.return_value = False
        app.get_modules.return_value = [module]
        ctx = _make_ctx(apps=[app])
        assert calc_has_user_case_management(ctx) is False
        mock_fn.assert_not_called()


class TestCalcHasOrganization(SimpleTestCase):

    @patch('corehq.apps.locations.models.LocationType.objects')
    def test_true_when_location_types_exist(self, mock_manager):
        mock_manager.filter.return_value.exists.return_value = True
        ctx = _make_ctx()
        assert calc_has_organization(ctx) is True

    @patch('corehq.apps.locations.models.LocationType.objects')
    def test_false_when_no_location_types(self, mock_manager):
        mock_manager.filter.return_value.exists.return_value = False
        ctx = _make_ctx()
        assert calc_has_organization(ctx) is False


class TestCalcUserProfiles(SimpleTestCase):

    @patch('corehq.apps.custom_data_fields.models.CustomDataFieldsDefinition.get')
    def test_counts_profiles(self, mock_get):
        mock_def = MagicMock()
        mock_def.get_profiles.return_value = [MagicMock(), MagicMock(), MagicMock()]
        mock_get.return_value = mock_def
        ctx = _make_ctx()
        assert calc_user_profiles(ctx) == 3

    @patch('corehq.apps.custom_data_fields.models.CustomDataFieldsDefinition.get')
    def test_zero_when_no_definition(self, mock_get):
        mock_get.return_value = None
        ctx = _make_ctx()
        assert calc_user_profiles(ctx) == 0

    @patch('corehq.apps.custom_data_fields.models.CustomDataFieldsDefinition.get')
    def test_zero_when_no_profiles(self, mock_get):
        mock_def = MagicMock()
        mock_def.get_profiles.return_value = []
        mock_get.return_value = mock_def
        ctx = _make_ctx()
        assert calc_user_profiles(ctx) == 0


class TestCalcHas2faRequired(SimpleTestCase):

    def test_true_when_enabled(self):
        ctx = _make_ctx(two_factor_auth=True)
        assert calc_has_2fa_required(ctx) is True

    def test_false_when_disabled(self):
        ctx = _make_ctx(two_factor_auth=False)
        assert calc_has_2fa_required(ctx) is False

    def test_false_when_attr_missing(self):
        domain_obj = MagicMock(spec=[])
        domain_obj.name = 'test'
        domain_obj.applications = MagicMock(return_value=[])
        ctx = DomainContext(domain_obj)
        assert calc_has_2fa_required(ctx) is False


class TestCalcHasShortenedTimeout(SimpleTestCase):

    def test_true_when_enabled(self):
        ctx = _make_ctx(secure_sessions=True)
        assert calc_has_shortened_timeout(ctx) is True

    def test_false_when_disabled(self):
        ctx = _make_ctx(secure_sessions=False)
        assert calc_has_shortened_timeout(ctx) is False


class TestCalcHasStrongPasswords(SimpleTestCase):

    def test_true_when_enabled(self):
        ctx = _make_ctx(strong_mobile_passwords=True)
        assert calc_has_strong_passwords(ctx) is True

    def test_false_when_disabled(self):
        ctx = _make_ctx(strong_mobile_passwords=False)
        assert calc_has_strong_passwords(ctx) is False


_feature_calcs = 'corehq.apps.data_analytics.feature_calcs'
@patch(f'{_feature_calcs}.BillingAccount.get_account_by_domain')
@patch(f'{_feature_calcs}.TrustedIdentityProvider.objects')
@patch(f'{_feature_calcs}.IdentityProvider.objects')
class TestCalcHasSso(SimpleTestCase):
    def test_true_when_owner_has_active_idp(
        self,
        mock_idp,
        mock_trusted,
        mock_get_owner,
    ):
        mock_get_owner.return_value = MagicMock()
        mock_idp.filter.return_value.exists.return_value = True
        mock_trusted.filter.return_value.exists.return_value = False
        ctx = _make_ctx()
        assert calc_has_sso(ctx) is True

    def test_true_when_domain_trusts_active_idp(
        self,
        mock_idp,
        mock_trusted,
        mock_get_owner,
    ):
        mock_get_owner.return_value = MagicMock()
        mock_idp.filter.return_value.exists.return_value = False
        mock_trusted.filter.return_value.exists.return_value = True
        ctx = _make_ctx()
        assert calc_has_sso(ctx) is True

    def test_false_when_no_sso(
        self,
        mock_idp,
        mock_trusted,
        mock_get_owner,
    ):
        mock_get_owner.return_value = MagicMock()
        mock_idp.filter.return_value.exists.return_value = False
        mock_trusted.filter.return_value.exists.return_value = False
        ctx = _make_ctx()
        assert calc_has_sso(ctx) is False

    def test_false_when_no_billing_account(
        self,
        mock_idp,
        mock_trusted,
        mock_get_owner,
    ):
        mock_get_owner.return_value = None
        mock_trusted.filter.return_value.exists.return_value = False
        ctx = _make_ctx()
        assert calc_has_sso(ctx) is False
        mock_idp.filter.assert_not_called()
