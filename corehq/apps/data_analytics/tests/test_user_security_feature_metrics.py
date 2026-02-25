from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from ..metric_registry import DomainContext
from ..feature_calcs import (
    calc_bulk_case_editing_sessions,
    calc_has_2fa_required,
    calc_has_data_dictionary,
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
    domain_obj.applications.return_value = apps or []
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


class TestCalcHasDataDictionary(SimpleTestCase):

    @patch('corehq.apps.data_dictionary.models.CaseProperty.objects')
    @patch('corehq.apps.data_dictionary.models.CaseType.objects')
    def test_false_when_no_case_types(self, mock_ct_manager, mock_cp_manager):
        mock_ct_manager.filter.return_value.exists.return_value = False
        ctx = _make_ctx()
        assert calc_has_data_dictionary(ctx) is False

    @patch('corehq.apps.data_dictionary.models.CaseProperty.objects')
    @patch('corehq.apps.data_dictionary.models.CaseType.objects')
    def test_true_when_case_type_has_description(
        self, mock_ct_manager, mock_cp_manager
    ):
        qs = mock_ct_manager.filter.return_value
        qs.exists.return_value = True
        qs.exclude.return_value.exclude.return_value.exists.return_value = True
        ctx = _make_ctx()
        assert calc_has_data_dictionary(ctx) is True

    @patch('corehq.apps.data_dictionary.models.CaseProperty.objects')
    @patch('corehq.apps.data_dictionary.models.CaseType.objects')
    def test_true_when_property_has_description(
        self, mock_ct_manager, mock_cp_manager
    ):
        # case types exist but none have descriptions
        ct_qs = mock_ct_manager.filter.return_value
        ct_qs.exists.return_value = True
        ct_qs.exclude.return_value.exclude.return_value.exists.return_value = False

        # first CaseProperty.objects.filter() call: property descriptions
        cp_qs1 = MagicMock()
        cp_qs1.exclude.return_value.exclude.return_value.exists.return_value = True

        mock_cp_manager.filter.return_value = cp_qs1
        ctx = _make_ctx()
        assert calc_has_data_dictionary(ctx) is True

    @patch('corehq.apps.data_dictionary.models.CaseProperty.objects')
    @patch('corehq.apps.data_dictionary.models.CaseType.objects')
    def test_true_when_property_has_group(
        self, mock_ct_manager, mock_cp_manager
    ):
        ct_qs = mock_ct_manager.filter.return_value
        ct_qs.exists.return_value = True
        ct_qs.exclude.return_value.exclude.return_value.exists.return_value = False

        # First call: property descriptions - no matches
        cp_qs_desc = MagicMock()
        cp_qs_desc.exclude.return_value.exclude.return_value.exists.return_value = False

        # Second call: property groups - has matches
        cp_qs_group = MagicMock()
        cp_qs_group.exists.return_value = True

        mock_cp_manager.filter.side_effect = [cp_qs_desc, cp_qs_group]
        ctx = _make_ctx()
        assert calc_has_data_dictionary(ctx) is True

    @patch('corehq.apps.data_dictionary.models.CaseProperty.objects')
    @patch('corehq.apps.data_dictionary.models.CaseType.objects')
    def test_false_when_no_descriptions_or_groups(
        self, mock_ct_manager, mock_cp_manager
    ):
        ct_qs = mock_ct_manager.filter.return_value
        ct_qs.exists.return_value = True
        ct_qs.exclude.return_value.exclude.return_value.exists.return_value = False

        # First call: property descriptions - no matches
        cp_qs_desc = MagicMock()
        cp_qs_desc.exclude.return_value.exclude.return_value.exists.return_value = False

        # Second call: property groups - no matches
        cp_qs_group = MagicMock()
        cp_qs_group.exists.return_value = False

        mock_cp_manager.filter.side_effect = [cp_qs_desc, cp_qs_group]
        ctx = _make_ctx()
        assert calc_has_data_dictionary(ctx) is False


class TestCalcHasSso(SimpleTestCase):

    @patch('corehq.apps.sso.models.TrustedIdentityProvider.objects')
    def test_true_when_sso_configured(self, mock_manager):
        mock_manager.filter.return_value.exists.return_value = True
        ctx = _make_ctx()
        assert calc_has_sso(ctx) is True

    @patch('corehq.apps.sso.models.TrustedIdentityProvider.objects')
    def test_false_when_no_sso(self, mock_manager):
        mock_manager.filter.return_value.exists.return_value = False
        ctx = _make_ctx()
        assert calc_has_sso(ctx) is False


class TestCalcBulkCaseEditingSessions(SimpleTestCase):

    @patch('corehq.apps.data_cleaning.models.BulkEditSession.objects')
    def test_counts_sessions(self, mock_manager):
        mock_manager.filter.return_value.count.return_value = 5
        ctx = _make_ctx()
        assert calc_bulk_case_editing_sessions(ctx) == 5

    @patch('corehq.apps.data_cleaning.models.BulkEditSession.objects')
    def test_zero_when_no_sessions(self, mock_manager):
        mock_manager.filter.return_value.count.return_value = 0
        ctx = _make_ctx()
        assert calc_bulk_case_editing_sessions(ctx) == 0
