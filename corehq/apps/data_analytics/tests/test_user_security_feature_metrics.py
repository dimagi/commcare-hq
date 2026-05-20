from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase, TestCase

from corehq.apps.sso.models import (
    IdentityProvider,
    LoginEnforcementType,
    TrustedIdentityProvider,
)
from corehq.apps.sso.tests import generator as sso_generator

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
from ..metric_registry import DomainContext


def _make_domain_context(apps=None, **domain_attrs):
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
        ctx = _make_domain_context()
        assert calc_mobile_user_groups(ctx) == 2

    @patch('corehq.apps.groups.models.Group.by_domain')
    def test_zero_when_no_groups(self, mock_by_domain):
        mock_by_domain.return_value = []
        ctx = _make_domain_context()
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
        app.get_forms.return_value = [form]
        ctx = _make_domain_context(apps=[app])
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
        ctx = _make_domain_context(apps=[app])
        assert calc_has_user_case_management(ctx) is False

    def test_false_when_no_apps(self):
        ctx = _make_domain_context(apps=[])
        assert calc_has_user_case_management(ctx) is False

    @patch('corehq.apps.app_manager.util.actions_use_usercase')
    def test_skips_forms_without_actions(self, mock_fn):
        form = MagicMock(spec=[])  # no 'actions' attribute
        module = MagicMock()
        module.get_forms.return_value = [form]
        app = MagicMock()
        app.is_remote_app.return_value = False
        app.get_modules.return_value = [module]
        ctx = _make_domain_context(apps=[app])
        assert calc_has_user_case_management(ctx) is False
        mock_fn.assert_not_called()


class TestCalcHasOrganization(SimpleTestCase):

    @patch('corehq.apps.locations.models.LocationType.objects')
    def test_true_when_location_types_exist(self, mock_manager):
        mock_manager.filter.return_value.exists.return_value = True
        ctx = _make_domain_context()
        assert calc_has_organization(ctx) is True

    @patch('corehq.apps.locations.models.LocationType.objects')
    def test_false_when_no_location_types(self, mock_manager):
        mock_manager.filter.return_value.exists.return_value = False
        ctx = _make_domain_context()
        assert calc_has_organization(ctx) is False


class TestCalcUserProfiles(SimpleTestCase):

    @patch('corehq.apps.custom_data_fields.models.CustomDataFieldsDefinition.get')
    def test_counts_profiles(self, mock_get):
        mock_def = MagicMock()
        mock_def.get_profiles.return_value = [MagicMock(), MagicMock(), MagicMock()]
        mock_get.return_value = mock_def
        ctx = _make_domain_context()
        assert calc_user_profiles(ctx) == 3

    @patch('corehq.apps.custom_data_fields.models.CustomDataFieldsDefinition.get')
    def test_zero_when_no_definition(self, mock_get):
        mock_get.return_value = None
        ctx = _make_domain_context()
        assert calc_user_profiles(ctx) == 0

    @patch('corehq.apps.custom_data_fields.models.CustomDataFieldsDefinition.get')
    def test_zero_when_no_profiles(self, mock_get):
        mock_def = MagicMock()
        mock_def.get_profiles.return_value = []
        mock_get.return_value = mock_def
        ctx = _make_domain_context()
        assert calc_user_profiles(ctx) == 0


class TestCalcHas2faRequired(SimpleTestCase):

    def test_true_when_enabled(self):
        ctx = _make_domain_context(two_factor_auth=True)
        assert calc_has_2fa_required(ctx) is True

    def test_false_when_disabled(self):
        ctx = _make_domain_context(two_factor_auth=False)
        assert calc_has_2fa_required(ctx) is False

    def test_false_when_attr_missing(self):
        domain_obj = MagicMock(spec=[])
        domain_obj.name = 'test'
        domain_obj.applications = MagicMock(return_value=[])
        ctx = DomainContext(domain_obj)
        assert calc_has_2fa_required(ctx) is False


class TestCalcHasShortenedTimeout(SimpleTestCase):

    def test_true_when_enabled(self):
        ctx = _make_domain_context(secure_sessions=True)
        assert calc_has_shortened_timeout(ctx) is True

    def test_false_when_disabled(self):
        ctx = _make_domain_context(secure_sessions=False)
        assert calc_has_shortened_timeout(ctx) is False


class TestCalcHasStrongPasswords(SimpleTestCase):

    def test_true_when_enabled(self):
        ctx = _make_domain_context(strong_mobile_passwords=True)
        assert calc_has_strong_passwords(ctx) is True

    def test_false_when_disabled(self):
        ctx = _make_domain_context(strong_mobile_passwords=False)
        assert calc_has_strong_passwords(ctx) is False


class TestCalcHasSso(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.account = sso_generator.get_billing_account_for_idp()
        cls.account.created_by_domain = 'test'
        cls.account.save()
        cls.other_account = sso_generator.get_billing_account_for_idp()

    def _create_idp(
        self,
        account,
        slug,
        is_active=True,
        login_enforcement_type=LoginEnforcementType.GLOBAL,
    ):
        return IdentityProvider.objects.create(
            owner=account,
            name=f'IdP {slug}',
            slug=slug,
            created_by='admin@dimagi.com',
            last_modified_by='admin@dimagi.com',
            is_active=is_active,
            login_enforcement_type=login_enforcement_type,
        )

    def _trust(self, idp):
        return TrustedIdentityProvider.objects.create(
            domain='test',
            identity_provider=idp,
            acknowledged_by='admin@dimagi.com',
        )

    def test_true_when_billing_account_has_active_idp_which_is_globally_enforced(self):
        self._create_idp(self.account, 'owner-active-global')
        assert calc_has_sso(_make_domain_context()) is True

    def test_false_when_owner_idp_inactive(self):
        self._create_idp(self.account, 'owner-inactive', is_active=False)
        assert calc_has_sso(_make_domain_context()) is False

    def test_false_when_owner_idp_not_globally_enforced(self):
        self._create_idp(
            self.account,
            'owner-test',
            login_enforcement_type=LoginEnforcementType.TEST,
        )
        assert calc_has_sso(_make_domain_context()) is False

    def test_true_when_domain_trusts_globally_enforced_idp(self):
        idp = self._create_idp(self.other_account, 'trusted-active-global')
        self._trust(idp)
        assert calc_has_sso(_make_domain_context()) is True

    def test_false_when_trusted_idp_inactive(self):
        idp = self._create_idp(
            self.other_account,
            'trusted-inactive',
            is_active=False,
        )
        self._trust(idp)
        assert calc_has_sso(_make_domain_context()) is False

    def test_false_when_trusted_idp_not_globally_enforced(self):
        idp = self._create_idp(
            self.other_account,
            'trusted-test',
            login_enforcement_type=LoginEnforcementType.TEST,
        )
        self._trust(idp)
        assert calc_has_sso(_make_domain_context()) is False

    def test_false_when_no_sso(self):
        assert calc_has_sso(_make_domain_context()) is False
