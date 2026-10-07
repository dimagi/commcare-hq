from django.test import TestCase
from django.urls import reverse

from corehq import privileges
from corehq.apps.app_manager.tests.app_factory import AppFactory
from corehq.apps.app_manager.tests.util import (
    get_simple_form,
    patch_validate_xform,
)
from corehq.apps.domain.models import Domain
from corehq.apps.es.apps import app_adapter
from corehq.apps.es.tests.utils import es_test
from corehq.apps.users.models import WebUser
from corehq.util.test_utils import privilege_enabled


@es_test(requires=[app_adapter], setup_class=True)
@privilege_enabled(privileges.USERCASE)
@patch_validate_xform()
class TestSaveCopy(TestCase):
    """
    A web user's first build flips ``has_built_app`` on the user, which
    saves the user and, in a domain with the USERCASE privilege, syncs
    their usercase. That sync needs a correctly wrapped ``WebUser``.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.domain_name = 'save-copy-test'
        cls.domain = Domain.get_or_create_with_name(cls.domain_name, is_active=True)
        cls.addClassCleanup(cls.domain.delete)

        cls.username = 'first-time-builder'
        cls.password = '***'
        cls.user = WebUser.create(cls.domain_name, cls.username, cls.password, None, None, is_admin=True)
        cls.user.eula.signed = True
        cls.user.save()
        cls.addClassCleanup(cls.user.delete, cls.domain_name, deleted_by=None)

        factory = AppFactory(cls.domain_name, name='first-build')
        m0, f0 = factory.new_basic_module('register', 'person')
        f0.source = get_simple_form(xmlns=f0.unique_id)
        cls.app = factory.app
        cls.app.save()
        cls.addClassCleanup(cls.app.delete)

    def test_first_build_sets_has_built_app(self):
        assert not self.user.has_built_app
        self.client.login(username=self.username, password=self.password)

        response = self.client.post(reverse('save_copy', args=[self.domain_name, self.app.get_id]))

        assert response.status_code == 200
        assert response.json()['saved_app']['version'] == 1
        assert WebUser.get_by_user_id(self.user.user_id).has_built_app
