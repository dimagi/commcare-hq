from mock import patch

from corehq.apps.app_manager.models import LinkedApplication, Module
from corehq.apps.app_manager.views.utils import get_blank_form_xml
from corehq.apps.linked_domain.const import (
    LINKED_MODELS_MAP,
    MODEL_APP,
    MODEL_CASE_SEARCH,
    MODEL_FLAGS,
    MODEL_USER_DATA,
)
from corehq.apps.linked_domain.models import AppLinkDetail, DomainLink
from corehq.apps.linked_domain.tasks import release_domain
from corehq.apps.linked_domain.tests.test_linked_apps import BaseLinkedAppsTest
from corehq.apps.users.models import WebUser
from corehq.util.test_utils import flag_enabled


class TestReleaseManager(BaseLinkedAppsTest):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = WebUser.create(cls.domain, 'fiona', 'secret', None, None)
        master1_module = cls.master1.add_module(Module.new_module('Module for master1', None))
        master1_module.new_form('Form for master1', 'en', get_blank_form_xml('Form for master1'))

    def _assert_domain_outcomes(self, result, domains):
        self.assertEqual(set(result.get('text', {}).keys()), set(domains))

    def _assert_error(self, result, domain, error):
        for actual in result.get('text', {}).get(domain, []):
            if error in actual:
                self.assertTrue(True)
                return
        self.fail(f"Could not find '{error}' in {domain}'s errors")

    def _model_status(self, _type, detail=None):
        return {
            'type': _type,
            'name': LINKED_MODELS_MAP[_type],
            'detail': detail,
        }

    def test_success(self):
        (successes, errors) = release_domain(self.domain, self.linked_domain, self.user.username, [
            self._model_status(MODEL_USER_DATA),
        ])
        self._assert_domain_outcomes(successes, {self.linked_domain})
        self._assert_domain_outcomes(errors, set())

    def test_exception(self):
        with patch('corehq.apps.linked_domain.updates.update_custom_data_models', side_effect=Exception('Boom!')):
            (successes, errors) = release_domain(self.domain, self.linked_domain, self.user.username, [
                self._model_status(MODEL_FLAGS),
                self._model_status(MODEL_USER_DATA),
            ])
        self._assert_domain_outcomes(successes, {self.linked_domain})
        self._assert_domain_outcomes(errors, {self.linked_domain})
        self._assert_error(errors, self.linked_domain, 'Boom!')

    @flag_enabled('SYNC_SEARCH_CASE_CLAIM')
    def test_case_claim_on(self):
        (successes, errors) = release_domain(self.domain, self.linked_domain, self.user.username, [
            self._model_status(MODEL_CASE_SEARCH),
        ], [self.linked_domain])
        self._assert_domain_outcomes(successes, {self.linked_domain})
        self._assert_domain_outcomes(errors, set())

    def test_case_claim_off(self):
        (successes, errors) = release_domain(self.domain, self.linked_domain, self.user.username, [
            self._model_status(MODEL_CASE_SEARCH),
        ])
        self._assert_domain_outcomes(successes, set())
        self._assert_domain_outcomes(errors, {self.linked_domain})
        self._assert_error(errors, self.linked_domain, 'Case claim flag is not on')

    def test_bad_domain(self):
        (successes, errors) = release_domain(self.domain, 'not-a-domain', self.user.username, [
            self._model_status(MODEL_FLAGS),
        ])
        self._assert_domain_outcomes(successes, set())
        self._assert_domain_outcomes(errors, {'not-a-domain'})
        self._assert_error(errors, 'not-a-domain', 'no longer linked')

    def test_app_not_found(self):
        (successes, errors) = release_domain(self.domain, self.linked_domain, self.user.username, [
            self._model_status(MODEL_APP, detail=AppLinkDetail(app_id='123').to_json()),
        ])
        self._assert_domain_outcomes(successes, set())
        self._assert_domain_outcomes(errors, {self.linked_domain})
        self._assert_error(errors, self.linked_domain, "Could not find app")

    @flag_enabled('MULTI_MASTER_LINKED_DOMAINS')
    def test_multi_master_app_fail(self):
        (successes, errors) = release_domain(self.domain, self.linked_domain, self.user.username, [
            self._model_status(MODEL_APP, detail=AppLinkDetail(app_id='123').to_json()),
        ])
        self._assert_domain_outcomes(successes, set())
        self._assert_domain_outcomes(errors, {self.linked_domain})
        self._assert_error(errors, self.linked_domain, "Multi master flag is in use")

    @patch('corehq.apps.app_manager.models.validate_xform', return_value=None)
    def test_app_build_and_release(self, *args):
        self._make_master1_build(True)
        original_version = self.linked_app.version
        (successes, errors) = release_domain(self.domain, self.linked_domain, self.user.username, [
            self._model_status(MODEL_APP, detail=AppLinkDetail(app_id=self.master1._id).to_json()),
        ], True)
        self._assert_domain_outcomes(successes, {self.linked_domain})
        self._assert_domain_outcomes(errors, set())
        self.linked_application = LinkedApplication.get(self.linked_app._id)
        self.assertEqual(original_version + 1, self.linked_application.version)
        self.assertTrue(self.linked_application.is_released)

    def test_app_update_then_fail(self):
        self._make_master1_build(True)
        # The missing validate_xform patch means this test will fail on travis, but make sure it also fails locally
        with patch('corehq.apps.app_manager.models.ApplicationBase.make_build', side_effect=Exception('Boom!')):
            (successes, errors) = release_domain(self.domain, self.linked_domain, self.user.username, [
                self._model_status(MODEL_APP, detail=AppLinkDetail(app_id=self.master1._id).to_json()),
            ], True)
            self._assert_error(errors, self.linked_domain, "Updated app but did not build or release: Boom!")
