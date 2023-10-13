from unittest.mock import patch

from corehq.apps.app_manager.models import Application, LinkedApplication
from corehq.apps.app_manager.tests.util import patch_validate_xform
from corehq.apps.linked_domain.const import (
    LINKED_MODELS_MAP,
    MODEL_APP,
    MODEL_CASE_SEARCH,
    MODEL_DIALER_SETTINGS,
    MODEL_FLAGS,
    MODEL_HMAC_CALLOUT_SETTINGS,
    MODEL_KEYWORD,
    MODEL_OTP_SETTINGS,
    MODEL_REPORT,
    MODEL_USER_DATA,
)
from corehq.apps.linked_domain.keywords import (
    create_linked_keyword,
    get_downstream_keyword,
)
from corehq.apps.linked_domain.models import (
    AppLinkDetail,
    KeywordLinkDetail,
    ReportLinkDetail,
)
from corehq.apps.linked_domain.tasks import ReleaseManager, release_domain
from corehq.apps.linked_domain.tests.test_linked_apps import BaseLinkedAppsTest
from corehq.apps.linked_domain.ucr import (
    create_linked_ucr,
    get_downstream_report,
)
from corehq.apps.sms.models import Keyword
from corehq.apps.userreports.tests.utils import (
    get_sample_data_source,
    get_sample_report_config,
)
from corehq.apps.users.models import WebUser
from corehq.util.test_utils import flag_enabled


class BaseReleaseManagerTest(BaseLinkedAppsTest):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = WebUser.create(cls.domain, 'fiona', 'secret', None, None)

    @classmethod
    def tearDownClass(cls):
        cls.user.delete(cls.domain, deleted_by=None)
        super().tearDownClass()

    def _linked_data_view_model(self, _type, detail=None):
        return {
            'type': _type,
            'name': LINKED_MODELS_MAP[_type],
            'detail': detail,
        }


class TestReleaseManager(BaseReleaseManagerTest):

    def _assert_release(self, models, domain=None, has_success=None, error=None, build_apps=False):
        domain = domain or self.linked_domain
        success_domains = set([domain]) if not error or has_success is True else set()
        error_domains = set([domain]) if error else set()

        (successes, errors) = release_domain(self.domain, domain, self.user.username, models,
                                             build_apps=build_apps)
        self.assertEqual(set(successes.get('text', {}).keys()), success_domains)
        self.assertEqual(set(errors.get('text', {}).keys()), error_domains)
        if errors:
            pass

    def test_success(self):
        self._assert_release([
            self._linked_data_view_model(MODEL_USER_DATA),
        ])

    def test_exception(self):
        with patch('corehq.apps.linked_domain.updates.update_custom_data_models', side_effect=Exception('Boom!')):
            self._assert_release([
                self._linked_data_view_model(MODEL_FLAGS),
                self._linked_data_view_model(MODEL_USER_DATA),
            ], has_success=True, error="Boom!")

    @flag_enabled('SYNC_SEARCH_CASE_CLAIM')
    def test_case_claim_on(self):
        self._assert_release([
            self._linked_data_view_model(MODEL_CASE_SEARCH),
        ])

    def test_case_claim_off(self):
        self._assert_release([
            self._linked_data_view_model(MODEL_CASE_SEARCH),
        ], error="Feature flag for Case Search Settings is not enabled")

    @flag_enabled('WIDGET_DIALER')
    def test_widget_dialer_on(self):
        self._assert_release([
            self._linked_data_view_model(MODEL_DIALER_SETTINGS),
        ])

    def test_widget_dialer_off(self):
        self._assert_release([
            self._linked_data_view_model(MODEL_DIALER_SETTINGS),
        ], error="Feature flag for Dialer Settings is not enabled")

    @flag_enabled('GAEN_OTP_SERVER')
    def test_otp_server_on(self):
        self._assert_release([
            self._linked_data_view_model(MODEL_OTP_SETTINGS),
        ])

    def test_otp_server_off(self):
        self._assert_release([
            self._linked_data_view_model(MODEL_OTP_SETTINGS),
        ], error="Feature flag for OTP Pass-through Settings is not enabled")

    @flag_enabled('HMAC_CALLOUT')
    def test_hmac_callout_on(self):
        self._assert_release([
            self._linked_data_view_model(MODEL_HMAC_CALLOUT_SETTINGS),
        ])

    def test_hmac_callout_off(self):
        self._assert_release([
            self._linked_data_view_model(MODEL_HMAC_CALLOUT_SETTINGS),
        ], error="Feature flag for Signed Callout is not enabled")

    def test_bad_domain(self):
        self._assert_release([
            self._linked_data_view_model(MODEL_FLAGS),
        ], domain='not-a-domain', error='no longer linked')

    def test_app_not_found(self):
        self._assert_release([
            self._linked_data_view_model(MODEL_APP, detail=AppLinkDetail(app_id='123').to_json()),
        ], error="Could not find app")

    @flag_enabled('MULTI_MASTER_LINKED_DOMAINS')
    def test_multi_master_app_fail(self):
        self._assert_release([
            self._linked_data_view_model(MODEL_APP, detail=AppLinkDetail(app_id='123').to_json()),
        ], error="Multi master flag is in use")

    @patch_validate_xform()
    def test_app_build_and_release(self, *args):
        self._make_master1_build(True)
        original_version = self.linked_app.version
        self._assert_release([
            self._linked_data_view_model(MODEL_APP, detail=AppLinkDetail(app_id=self.master1._id).to_json()),
        ], build_apps=True)
        self.linked_application = LinkedApplication.get(self.linked_app._id)
        self.assertEqual(original_version + 1, self.linked_application.version)
        self.assertTrue(self.linked_application.is_released)

    @patch_validate_xform()
    def test_app_update_then_fail(self):
        self._make_master1_build(True)
        # The missing validate_xform patch means this test will fail on travis, but make sure it also fails locally
        with patch('corehq.apps.app_manager.models.ApplicationBase.make_build', side_effect=Exception('Boom!')):
            self._assert_release([
                self._linked_data_view_model(MODEL_APP, detail=AppLinkDetail(app_id=self.master1._id).to_json()),
            ], error="Updated app but did not build or release: Boom!", build_apps=True)

    def test_no_error_domains_on_init(self):
        manager = ReleaseManager(self.domain, self.user.username)
        self.assertEqual(manager.get_error_domain_count(), 0)

    def test_error_count_shows_number_of_errored_domains(self):
        manager = ReleaseManager(self.domain, self.user.username)
        manager.add_error('test-domain1', 'Something went wrong')
        manager.add_error('test-domain2', 'Something different went wrong')
        self.assertEqual(manager.get_error_domain_count(), 2)

    def test_error_count_does_not_count_multiple_errors(self):
        manager = ReleaseManager(self.domain, self.user.username)
        manager.add_error('test-domain', 'Error1')
        manager.add_error('test-domain', 'Error2')
        self.assertEqual(manager.get_error_domain_count(), 1)

    def test_no_success_domains_on_init(self):
        manager = ReleaseManager(self.domain, self.user.username)
        self.assertEqual(manager.get_success_domain_count(), 0)

    def test_success_count_shows_number_of_successful_domains(self):
        manager = ReleaseManager(self.domain, self.user.username)
        manager.add_success('test-domain1', 'It worked!')
        manager.add_success('test-domain2', 'It also worked!')
        self.assertEqual(manager.get_success_domain_count(), 2)

    def test_success_count_does_not_count_multiple_successes(self):
        manager = ReleaseManager(self.domain, self.user.username)
        manager.add_success('test-domain', 'Object1')
        manager.add_success('test-domain', 'Object2')
        self.assertEqual(manager.get_success_domain_count(), 1)

    def test_successes_are_idempotent(self):
        # This test exists because '_get_successes()' was inserting a new key into the error dictionary,
        # causing the success count to increase.
        # The success count should be unaffected by any calls to '_get_successes()'
        manager = ReleaseManager(self.domain, self.user.username)
        manager._get_successes('test-domain')
        self.assertEqual(manager.get_success_domain_count(), 0)

    def test_errors_are_idempotent(self):
        # This test exists because '_get_errors()' was inserting a new key into the error dictionary,
        # causing the error count to increase.
        # The error count should be unaffected by any calls to '_get_errors()'
        manager = ReleaseManager(self.domain, self.user.username)
        manager._get_errors('test-domain')
        self.assertEqual(manager.get_error_domain_count(), 0)


class TestReleaseApp(BaseReleaseManagerTest):

    def test_app_not_pushed_if_not_found(self):
        unpushed_app = Application.new_app(self.domain, "Not Yet Pushed App")
        unpushed_app.save()
        self.addCleanup(unpushed_app.delete)
        model = self._linked_data_view_model(MODEL_APP, detail=AppLinkDetail(app_id=unpushed_app._id).to_json())
        manager = ReleaseManager(self.domain, self.user.username)

        errors = manager._release_app(self.domain_link, model, manager.user)

        self.assertTrue("Could not find app" in errors)


class TestReleaseReport(BaseReleaseManagerTest):

    def _create_new_report(self):
        self.data_source = get_sample_data_source()
        self.data_source.domain = self.domain
        self.data_source.save()

        self.report = get_sample_report_config()
        self.report.config_id = self.data_source.get_id
        self.report.domain = self.domain
        self.report.save()
        return self.report

    def test_already_linked_report_is_pushed(self):
        new_report = self._create_new_report()
        new_report.title = "Title"
        new_report.save()
        self.addCleanup(new_report.delete)
        linked_report_info = create_linked_ucr(self.domain_link, new_report.get_id)
        self.addCleanup(linked_report_info.report.delete)
        # after creating the link, update the upstream report
        new_report.title = "Updated Title"
        new_report.save()
        model = self._linked_data_view_model(
            MODEL_REPORT, detail=ReportLinkDetail(report_id=new_report.get_id).to_json()
        )
        manager = ReleaseManager(self.domain, self.user.username)

        errors = manager._release_report(self.domain_link, model, 'test-user')
        self.assertIsNone(errors)

        downstream_report = get_downstream_report(self.linked_domain, new_report.get_id)
        self.assertIsNotNone(downstream_report)
        self.assertEqual("Updated Title", downstream_report.title)

    def test_report_pushed_if_not_found(self):
        unpushed_report = self._create_new_report()
        self.addCleanup(unpushed_report.delete)
        model = self._linked_data_view_model(
            MODEL_REPORT,
            detail=ReportLinkDetail(report_id=unpushed_report.get_id).to_json()
        )
        manager = ReleaseManager(self.domain, self.user.username)

        errors = manager._release_report(self.domain_link, model, 'test-user')
        self.assertIsNone(errors)

        downstream_report = get_downstream_report(self.linked_domain, unpushed_report.get_id)
        self.addCleanup(downstream_report.delete)
        self.assertIsNotNone(downstream_report)


class TestReleaseKeyword(BaseReleaseManagerTest):

    def _create_new_keyword(self, keyword_name):
        keyword = Keyword(
            domain=self.domain_link.master_domain,
            keyword=keyword_name,
            description="The description",
            override_open_sessions=True,
        )
        keyword.save()
        return keyword

    def test_already_linked_keyword_is_pushed(self):
        keyword = self._create_new_keyword('keyword')
        self.addCleanup(keyword.delete)
        linked_keyword_id = create_linked_keyword(self.domain_link, keyword.id)
        self.addCleanup(Keyword(id=linked_keyword_id).delete)
        # after creating the link, update the upstream keyword
        keyword.keyword = "updated-keyword"
        keyword.save()
        model = self._linked_data_view_model(
            MODEL_KEYWORD, detail=KeywordLinkDetail(keyword_id=str(keyword.id)).to_json()
        )
        manager = ReleaseManager(self.domain, self.user.username)

        errors = manager._release_keyword(self.domain_link, model, 'test-user')
        self.assertIsNone(errors)

        downstream_keyword = get_downstream_keyword(self.linked_domain, keyword.id)
        self.addCleanup(downstream_keyword.delete)
        self.assertIsNotNone(downstream_keyword)
        self.assertEqual("updated-keyword", downstream_keyword.keyword)

    def test_keyword_pushed_if_not_found(self):
        keyword = self._create_new_keyword('keyword')
        self.addCleanup(keyword.delete)
        model = self._linked_data_view_model(
            MODEL_KEYWORD, detail=KeywordLinkDetail(keyword_id=str(keyword.id)).to_json()
        )

        manager = ReleaseManager(self.domain, self.user.username)

        errors = manager._release_keyword(self.domain_link, model, 'test-user')
        self.assertIsNone(errors)

        downstream_keyword = get_downstream_keyword(self.linked_domain, keyword.id)
        self.addCleanup(downstream_keyword.delete)
        self.assertIsNotNone(downstream_keyword)
        self.assertEqual("keyword", downstream_keyword.keyword)
