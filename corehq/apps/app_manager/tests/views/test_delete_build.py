from django.test import TestCase
from django.urls import reverse

from corehq.apps.app_manager.dbaccessors import get_app
from corehq.apps.app_manager.tests.app_factory import AppFactory
from corehq.apps.app_manager.tests.util import (
    get_simple_form,
    patch_validate_xform,
)
from corehq.apps.domain.models import Domain
from corehq.apps.users.models import WebUser
from corehq.util.test_utils import flag_enabled


class TestDeleteBuild(TestCase):
    @classmethod
    @patch_validate_xform()
    def setUpClass(cls):
        super().setUpClass()

        cls.domain_name = 'delete-build-test'
        cls.domain = Domain.get_or_create_with_name(
            cls.domain_name, is_active=True
        )
        cls.addClassCleanup(cls.domain.delete)

        cls.user = WebUser.create(
            cls.domain.name,
            'build-deleter',
            '*******',
            None,
            None,
            is_admin=True,
        )
        cls.addClassCleanup(cls.user.delete, cls.domain.name, deleted_by=None)

        factory = AppFactory(cls.domain_name, name='app')
        m0, f0 = factory.new_basic_module('register', 'case')
        f0.source = get_simple_form(xmlns=f0.unique_id)
        cls.app = factory.app
        cls.app.save()

        cls.build = cls.app.make_build()
        cls.build.save()

    def setUp(self):
        self.client.force_login(self.user.get_django_user())

    def _delete_build(self):
        url = reverse('delete_copy', args=(self.domain_name, self.app.get_id))
        return self.client.post(url, {'saved_app': self.build.get_id})

    def _restore_build(self):
        build = get_app(self.domain_name, self.build.get_id)
        build.doc_type = 'Application'
        build.save(increment_version=False)

    @flag_enabled('SUPPORT')
    def test_delete_build_with_support_flag(self):
        self.addCleanup(self._restore_build)
        response = self._delete_build()

        assert response.status_code == 200
        assert (
            get_app(self.domain_name, self.build.get_id).doc_type
            == 'Application-Deleted'
        )

    def test_delete_build_without_support_flag_is_rejected(self):
        response = self._delete_build()

        assert response.status_code == 404
        assert (
            get_app(self.domain_name, self.build.get_id).doc_type
            == 'Application'
        )
