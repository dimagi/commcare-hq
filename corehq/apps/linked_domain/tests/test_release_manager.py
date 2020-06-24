from mock import patch

from corehq.apps.linked_domain.const import (
    LINKED_MODELS_MAP,
    MODEL_FLAGS,
    MODEL_USER_DATA,
)
from corehq.apps.linked_domain.tasks import ReleaseManager
from corehq.apps.linked_domain.tests.test_linked_apps import BaseLinkedAppsTest
from corehq.apps.users.models import WebUser


class TestReleaseManager(BaseLinkedAppsTest):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = WebUser.create(cls.domain, 'fionaa', 'secret', None, None)
        cls.manager = ReleaseManager(cls.domain, cls.user)

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()

    def _assert_error_domains(self, domains):
        self.assertEqual(set(self.manager.errors_by_domain.keys()), domains)

    def _assert_error(self, domain, error):
        for actual in self.manager.errors_by_domain.get(domain, []):
            if error in actual:
                self.assertTrue(True)
                return
        self.fail(f"Could not find '{error}' in {domain}'s errors")

    def _assert_success_domains(self, domains):
        self.assertEqual(set(self.manager.successes_by_domain.keys()), domains)

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
        self._assert_error_domains(set())
        self._assert_success_domains({self.linked_domain})

    def test_exception(self):
        with patch('corehq.apps.linked_domain.updates.update_custom_data_models', side_effect=Exception('Boom!')):
            self.manager.release([
                self._model_status(MODEL_FLAGS),
                self._model_status(MODEL_USER_DATA),
            ], [self.linked_domain])
        self._assert_error_domains({self.linked_domain})
        self._assert_error(self.linked_domain, 'Boom!')
        self._assert_success_domains({self.linked_domain})
