from mock import patch

from corehq.apps.app_manager.models import LinkedApplication, Module
from corehq.apps.app_manager.tests.util import patch_validate_xform
from corehq.apps.app_manager.views.utils import get_blank_form_xml
from corehq.apps.linked_domain.const import (
    LINKED_MODELS_MAP,
    MODEL_APP,
    MODEL_CASE_SEARCH,
    MODEL_FLAGS,
    MODEL_USER_DATA,
    MODEL_DATA_DICTIONARY,
    MODEL_DIALER_SETTINGS,
    MODEL_OTP_SETTINGS,
    MODEL_HMAC_CALLOUT_SETTINGS,
)
from corehq.apps.linked_domain.models import AppLinkDetail
from corehq.apps.linked_domain.tasks import release_domain
from corehq.apps.linked_domain.tests.test_linked_apps import BaseLinkedAppsTest
from corehq.apps.users.models import WebUser
from corehq.util.test_utils import flag_enabled


class TestReleaseManager(BaseLinkedAppsTest):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = WebUser.create(cls.domain, 'fiona', 'secret', None, None)

    def _linked_data_view_model(self, _type, detail=None):
        return {
            'type': _type,
            'name': LINKED_MODELS_MAP[_type],
            'detail': detail,
        }

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

    @flag_enabled('DATA_DICTIONARY')
    def test_data_dictionary_on(self):
        self._assert_release([
            self._linked_data_view_model(MODEL_DATA_DICTIONARY),
        ])

    def test_data_dictionary_off(self):
        self._assert_release([
            self._linked_data_view_model(MODEL_DATA_DICTIONARY),
        ], error="Feature flag for Data Dictionary is not enabled")

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
