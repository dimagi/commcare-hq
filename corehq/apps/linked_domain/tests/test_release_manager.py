from mock import patch

from corehq.apps.linked_domain.const import (
    LINKED_MODELS_MAP,
    MODEL_APP,
    MODEL_CASE_SEARCH,
    MODEL_FLAGS,
    MODEL_USER_DATA,
)
from corehq.apps.linked_domain.models import AppLinkDetail
from corehq.apps.linked_domain.tasks import ReleaseManager
from corehq.apps.linked_domain.tests.test_linked_apps import BaseLinkedAppsTest
from corehq.apps.users.models import WebUser
from corehq.util.test_utils import flag_enabled


class TestReleaseManager(BaseLinkedAppsTest):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = WebUser.create(cls.domain, 'fionaa', 'secret', None, None)
        cls.manager = ReleaseManager(cls.domain, cls.user)

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()

    def _assert_domain_outcomes(self, success_domains, error_domains):
        self.assertEqual(set(self.manager.successes_by_domain.keys()), success_domains)
        self.assertEqual(set(self.manager.errors_by_domain.keys()), error_domains)

    def _assert_error(self, domain, error):
        for actual in self.manager.errors_by_domain.get(domain, []):
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
