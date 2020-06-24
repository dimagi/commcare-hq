from corehq.apps.linked_domain.const import (
    LINKED_MODELS_MAP,
    MODEL_USER_DATA,
)
from corehq.apps.linked_domain.tasks import ReleaseManager
from corehq.apps.linked_domain.tests.test_linked_apps import BaseLinkedAppsTest
from corehq.apps.users.models import WebUser


class TestReleaseManager(BaseLinkedAppsTest):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = WebUser.create(cls.domain, 'fiona', 'secret', None, None)

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()

    def test_success(self):
        manager = ReleaseManager(self.domain, self.user)
        manager.release([{
            'type': MODEL_USER_DATA,
            'name': LINKED_MODELS_MAP[MODEL_USER_DATA],
            'detail': None,
        }], [self.linked_domain])
        self.assertEqual(manager.errors_by_domain, {})
        self.assertEqual(set(manager.successes_by_domain.keys()), {self.linked_domain})
