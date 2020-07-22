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
from corehq.apps.linked_domain.tasks import ReleaseManager
from corehq.apps.linked_domain.tests.test_linked_apps import BaseLinkedAppsTest
from corehq.apps.users.models import WebUser
from corehq.util.test_utils import flag_enabled


class TestReleaseManager(BaseLinkedAppsTest):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = WebUser.create(cls.domain, 'fiona', 'secret', None, None)
        cls.manager = ReleaseManager(cls.domain, cls.user)
        master1_module = cls.master1.add_module(Module.new_module('Module for master1', None))
        master1_module.new_form('Form for master1', 'en', get_blank_form_xml('Form for master1'))
        cls.extra_domain = 'antarctica'
        cls.extra_domain_link = DomainLink.link_domains(cls.extra_domain, cls.domain)

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        cls.extra_domain_link.delete()

    def _assert_domain_outcomes(self, success_domains, error_domains):
        self.assertEqual(
            set(self.manager.successes_by_domain.get('text', {}).keys()),
            success_domains
        )
        self.assertEqual(
            set(self.manager.errors_by_domain.get('text', {}).keys()),
            error_domains
        )

    def _assert_error(self, domain, error):
        for actual in self.manager.errors_by_domain.get('text', {}).get(domain, []):
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
        self.manager.release([
            self._model_status(MODEL_USER_DATA),
        ], [self.linked_domain])
        self._assert_domain_outcomes({self.linked_domain}, set())

    def test_exception(self):
        with patch('corehq.apps.linked_domain.updates.update_custom_data_models', side_effect=Exception('Boom!')):
            self.manager.release([
                self._model_status(MODEL_FLAGS),
                self._model_status(MODEL_USER_DATA),
            ], [self.linked_domain])
        self._assert_domain_outcomes({self.linked_domain}, {self.linked_domain})
        self._assert_error(self.linked_domain, 'Boom!')

    @flag_enabled('SYNC_SEARCH_CASE_CLAIM')
    def test_case_claim_on(self):
        self.manager.release([
            self._model_status(MODEL_CASE_SEARCH),
        ], [self.linked_domain])
        self._assert_domain_outcomes({self.linked_domain}, set())

    def test_case_claim_off(self):
        self.manager.release([
            self._model_status(MODEL_CASE_SEARCH),
        ], [self.linked_domain])
        self._assert_domain_outcomes(set(), {self.linked_domain})
        self._assert_error(self.linked_domain, 'Case claim flag is not on')

    def test_bad_domain(self):
        self.manager.release([
            self._model_status(MODEL_FLAGS),
        ], [self.linked_domain, 'not-a-domain'])
        self._assert_domain_outcomes({self.linked_domain}, {'not-a-domain'})
        self._assert_error('not-a-domain', 'no longer linked')

    def test_app_not_found(self):
        self.manager.release([
            self._model_status(MODEL_APP, detail=AppLinkDetail(app_id='123').to_json()),
        ], [self.linked_domain])
        self._assert_domain_outcomes(set(), {self.linked_domain})
        self._assert_error(self.linked_domain, "Could not find app")

    @flag_enabled('MULTI_MASTER_LINKED_DOMAINS')
    def test_multi_master_app_fail(self):
        self.manager.release([
            self._model_status(MODEL_APP, detail=AppLinkDetail(app_id='123').to_json()),
        ], [self.linked_domain])
        self._assert_domain_outcomes(set(), {self.linked_domain})
        self._assert_error(self.linked_domain, "Multi master flag is in use")

    @patch('corehq.apps.app_manager.models.validate_xform', return_value=None)
    def test_app_build_and_release(self, *args):
        self._make_master1_build(True)
        original_version = self.linked_app.version
        self.manager.release([
            self._model_status(MODEL_APP, detail=AppLinkDetail(app_id=self.master1._id).to_json()),
        ], [self.linked_domain], True)
        self._assert_domain_outcomes({self.linked_domain}, set())
        self.linked_application = LinkedApplication.get(self.linked_app._id)
        self.assertEqual(original_version + 1, self.linked_application.version)
        self.assertTrue(self.linked_application.is_released)

    def test_app_update_then_fail(self):
        self._make_master1_build(True)
        # The missing validate_xform patch means this test will fail on travis, but make sure it also fails locally
        with patch('corehq.apps.app_manager.models.ApplicationBase.make_build', side_effect=Exception('Boom!')):
            self.manager.release([
                self._model_status(MODEL_APP, detail=AppLinkDetail(app_id=self.master1._id).to_json()),
            ], [self.linked_domain], True)
            self._assert_error(self.linked_domain, "Updated app but did not build or release: Boom!")

    def test_multiple_domains(self):
        self.manager.release([
            self._model_status(MODEL_FLAGS),
        ], [self.linked_domain, self.extra_domain])
        self._assert_domain_outcomes({self.linked_domain, self.extra_domain}, set())
