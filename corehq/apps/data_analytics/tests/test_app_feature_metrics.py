from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from ..feature_calcs import (
    calc_bulk_case_editing_sessions,
    calc_has_app_profiles,
    calc_has_case_management,
    calc_has_custom_branding,
    calc_has_eof_navigation,
    calc_has_multimedia,
    calc_has_save_to_case,
    calc_has_web_apps,
)
from ..metric_registry import DomainContext


def _make_domain_context(apps=None, **domain_attrs):
    domain_obj = MagicMock()
    domain_obj.name = 'test'
    domain_obj.full_applications.return_value = apps or []
    domain_obj.has_custom_logo = False
    for k, v in domain_attrs.items():
        setattr(domain_obj, k, v)
    return DomainContext(domain_obj)


def _make_app_with_modules(modules):
    app = MagicMock()
    app.is_remote_app.return_value = False
    app.get_modules.return_value = modules
    app.multimedia_map = {}
    app.cloudcare_enabled = False
    app.build_profiles = {}
    app.logo_refs = {}
    return app


def _make_module(case_type='', forms=None):
    module = MagicMock()
    module.case_type = case_type
    module.get_forms.return_value = forms or []
    return module


class TestCalcHasMultimedia(SimpleTestCase):

    def test_true_when_app_has_multimedia(self):
        app = MagicMock()
        app.is_remote_app.return_value = False
        app.multimedia_map = {'image.png': {'path': '/img.png'}}
        ctx = _make_domain_context(apps=[app])
        assert calc_has_multimedia(ctx) is True

    def test_false_when_no_multimedia(self):
        app = MagicMock()
        app.is_remote_app.return_value = False
        app.multimedia_map = {}
        ctx = _make_domain_context(apps=[app])
        assert calc_has_multimedia(ctx) is False

    def test_false_when_no_apps(self):
        ctx = _make_domain_context(apps=[])
        assert calc_has_multimedia(ctx) is False


class TestCalcHasCaseManagement(SimpleTestCase):

    def test_true_when_module_has_case_type(self):
        module = _make_module(case_type='patient')
        app = _make_app_with_modules([module])
        ctx = _make_domain_context(apps=[app])
        assert calc_has_case_management(ctx) is True

    def test_false_when_no_case_type(self):
        module = _make_module(case_type='')
        app = _make_app_with_modules([module])
        ctx = _make_domain_context(apps=[app])
        assert calc_has_case_management(ctx) is False

    def test_false_when_no_apps(self):
        ctx = _make_domain_context(apps=[])
        assert calc_has_case_management(ctx) is False

    def test_true_with_multiple_modules(self):
        mod_no_case = _make_module(case_type='')
        mod_with_case = _make_module(case_type='household')
        app = _make_app_with_modules([mod_no_case, mod_with_case])
        ctx = _make_domain_context(apps=[app])
        assert calc_has_case_management(ctx) is True


class TestCalcHasEofNavigation(SimpleTestCase):

    def test_true_when_form_has_non_default_workflow(self):
        form = MagicMock()
        form.post_form_workflow = 'module_default'
        module = _make_module(forms=[form])
        app = _make_app_with_modules([module])
        ctx = _make_domain_context(apps=[app])
        assert calc_has_eof_navigation(ctx) is True

    def test_false_when_all_default_workflow(self):
        form = MagicMock()
        form.post_form_workflow = 'default'
        module = _make_module(forms=[form])
        app = _make_app_with_modules([module])
        ctx = _make_domain_context(apps=[app])
        assert calc_has_eof_navigation(ctx) is False

    def test_false_when_no_apps(self):
        ctx = _make_domain_context(apps=[])
        assert calc_has_eof_navigation(ctx) is False

    def test_false_when_no_forms(self):
        module = _make_module(forms=[])
        app = _make_app_with_modules([module])
        ctx = _make_domain_context(apps=[app])
        assert calc_has_eof_navigation(ctx) is False


class TestCalcHasWebApps(SimpleTestCase):

    def test_true_when_cloudcare_enabled(self):
        app = MagicMock()
        app.is_remote_app.return_value = False
        app.cloudcare_enabled = True
        ctx = _make_domain_context(apps=[app])
        assert calc_has_web_apps(ctx) is True

    def test_false_when_cloudcare_disabled(self):
        app = MagicMock()
        app.is_remote_app.return_value = False
        app.cloudcare_enabled = False
        ctx = _make_domain_context(apps=[app])
        assert calc_has_web_apps(ctx) is False

    def test_false_when_no_apps(self):
        ctx = _make_domain_context(apps=[])
        assert calc_has_web_apps(ctx) is False


class TestCalcHasAppProfiles(SimpleTestCase):

    def test_true_when_build_profiles_exist(self):
        app = MagicMock()
        app.is_remote_app.return_value = False
        app.build_profiles = {'profile1': {'langs': ['en']}}
        ctx = _make_domain_context(apps=[app])
        assert calc_has_app_profiles(ctx) is True

    def test_false_when_no_build_profiles(self):
        app = MagicMock()
        app.is_remote_app.return_value = False
        app.build_profiles = {}
        ctx = _make_domain_context(apps=[app])
        assert calc_has_app_profiles(ctx) is False

    def test_false_when_no_apps(self):
        ctx = _make_domain_context(apps=[])
        assert calc_has_app_profiles(ctx) is False


class TestCalcHasSaveToCase(SimpleTestCase):
    """Save To Case is a Vellum question type that writes data to a case
    from inside a repeat group. It is detected via
    form.get_save_to_case_updates(), which returns a non-empty dict
    when Save To Case questions are present.
    """

    def test_true_when_form_has_save_to_case(self):
        form = MagicMock()
        form.get_save_to_case_updates.return_value = {'patient': {'name', 'dob'}}
        module = _make_module(forms=[form])
        app = _make_app_with_modules([module])
        ctx = _make_domain_context(apps=[app])
        assert calc_has_save_to_case(ctx) is True

    def test_false_when_save_to_case_updates_empty(self):
        form = MagicMock()
        form.get_save_to_case_updates.return_value = {}
        module = _make_module(forms=[form])
        app = _make_app_with_modules([module])
        ctx = _make_domain_context(apps=[app])
        assert calc_has_save_to_case(ctx) is False

    def test_false_when_form_has_no_get_save_to_case_updates(self):
        # Some form types (e.g. shadow forms) may not have this method
        form = MagicMock(spec=[])
        module = _make_module(forms=[form])
        app = _make_app_with_modules([module])
        ctx = _make_domain_context(apps=[app])
        assert calc_has_save_to_case(ctx) is False

    def test_false_when_no_apps(self):
        ctx = _make_domain_context(apps=[])
        assert calc_has_save_to_case(ctx) is False


class TestCalcBulkCaseEditingSessions(SimpleTestCase):

    @patch('corehq.apps.data_cleaning.models.BulkEditSession.objects')
    def test_counts_sessions(self, mock_manager):
        mock_manager.filter.return_value.count.return_value = 5
        ctx = _make_domain_context()
        assert calc_bulk_case_editing_sessions(ctx) == 5

    @patch('corehq.apps.data_cleaning.models.BulkEditSession.objects')
    def test_zero_when_no_sessions(self, mock_manager):
        mock_manager.filter.return_value.count.return_value = 0
        ctx = _make_domain_context()
        assert calc_bulk_case_editing_sessions(ctx) == 0


class TestCalcHasCustomBranding(SimpleTestCase):

    def test_true_when_domain_has_custom_logo(self):
        ctx = _make_domain_context(apps=[], has_custom_logo=True)
        assert calc_has_custom_branding(ctx) is True

    def test_true_when_app_has_logo_refs(self):
        app = MagicMock()
        app.is_remote_app.return_value = False
        app.logo_refs = {'hq_logo_android_home': 'path/to/logo.png'}
        ctx = _make_domain_context(apps=[app], has_custom_logo=False)
        assert calc_has_custom_branding(ctx) is True

    def test_false_when_no_branding(self):
        app = MagicMock()
        app.is_remote_app.return_value = False
        app.logo_refs = {}
        ctx = _make_domain_context(apps=[app], has_custom_logo=False)
        assert calc_has_custom_branding(ctx) is False

    def test_false_when_no_apps(self):
        ctx = _make_domain_context(apps=[], has_custom_logo=False)
        assert calc_has_custom_branding(ctx) is False
