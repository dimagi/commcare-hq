from django.test import TestCase

from corehq.apps.app_manager.models import Application, ReportModule, ReportAppConfig
from corehq.apps.cloudcare.utils import should_restrict_web_apps_usage
from corehq.apps.domain.shortcuts import create_domain
from corehq.util.test_utils import flag_disabled, flag_enabled


class TestShouldRestrictWebAppsUsage(TestCase):

    @flag_disabled("ALLOW_WEB_APPS_RESTRICTION")
    @flag_disabled("MOBILE_UCR")
    def test_returns_false_if_domain_ucr_count_is_under_limit_and_neither_toggle_is_enable(self):
        self._create_app_with_reports(report_count=0)
        with self.settings(MAX_MOBILE_UCR_LIMIT=1):
            result = should_restrict_web_apps_usage(self.domain.name)
        self.assertFalse(result)

    @flag_disabled("ALLOW_WEB_APPS_RESTRICTION")
    @flag_disabled("MOBILE_UCR")
    def test_returns_false_if_domain_ucr_count_exceeds_limit_and_neither_toggle_is_enabled(self):
        self._create_app_with_reports(report_count=2)
        with self.settings(MAX_MOBILE_UCR_LIMIT=1):
            result = should_restrict_web_apps_usage(self.domain.name)
        self.assertFalse(result)

    @flag_enabled("ALLOW_WEB_APPS_RESTRICTION")
    @flag_disabled("MOBILE_UCR")
    def test_returns_false_if_domain_ucr_count_exceeds_limit_and_ALLOW_WEB_APPS_RESTRICTION_is_enabled(self):
        self._create_app_with_reports(report_count=2)
        with self.settings(MAX_MOBILE_UCR_LIMIT=1):
            result = should_restrict_web_apps_usage(self.domain.name)
        self.assertFalse(result)

    @flag_disabled("ALLOW_WEB_APPS_RESTRICTION")
    @flag_enabled("MOBILE_UCR")
    def test_returns_false_if_domain_ucr_count_exceeds_limit_and_MOBILE_UCR_is_enabled(self):
        self._create_app_with_reports(report_count=2)
        with self.settings(MAX_MOBILE_UCR_LIMIT=1):
            result = should_restrict_web_apps_usage(self.domain.name)
        self.assertFalse(result)

    @flag_enabled("ALLOW_WEB_APPS_RESTRICTION")
    @flag_enabled("MOBILE_UCR")
    def test_returns_false_if_domain_ucr_count_is_under_limit_and_both_flags_are_enabled(self):
        self._create_app_with_reports(report_count=1)
        with self.settings(MAX_MOBILE_UCR_LIMIT=2):
            result = should_restrict_web_apps_usage(self.domain.name)
        self.assertFalse(result)

    @flag_enabled("ALLOW_WEB_APPS_RESTRICTION")
    @flag_enabled("MOBILE_UCR")
    def test_returns_false_if_domain_ucr_count_equals_limit_and_both_flags_are_enabled(self):
        self._create_app_with_reports(report_count=1)
        with self.settings(MAX_MOBILE_UCR_LIMIT=1):
            result = should_restrict_web_apps_usage(self.domain.name)
        self.assertFalse(result)

    @flag_enabled("ALLOW_WEB_APPS_RESTRICTION")
    @flag_enabled("MOBILE_UCR")
    def test_returns_true_if_domain_ucr_count_exceeds_limit_and_both_flags_are_enabled(self):
        self._create_app_with_reports(report_count=2)
        with self.settings(MAX_MOBILE_UCR_LIMIT=1):
            result = should_restrict_web_apps_usage(self.domain.name)
            self.assertTrue(result)

    def _create_app_with_reports(self, report_count=1):
        configs = []
        for idx in range(report_count):
            configs.append(ReportAppConfig(report_id=f'{idx}'))
        report_module = ReportModule(name={"test": "Reports"}, report_configs=configs)
        self.app = Application(domain=self.domain.name, version=1, modules=[report_module])
        self.app.save()
        self.addCleanup(self.app.delete)

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.domain = create_domain('test-web-apps-restriction')
        cls.addClassCleanup(cls.domain.delete)
