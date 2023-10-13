from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
from django.test import TestCase
from django.test.client import RequestFactory

from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.ota.decorators import require_mobile_access
from corehq.apps.users.models import CommCareUser, UserRole, WebUser
from corehq.apps.users.role_utils import (
    UserRolePresets,
    initialize_domain_with_default_roles,
)
from corehq.util.test_utils import flag_enabled


@flag_enabled('SYNC_SEARCH_CASE_CLAIM')
class TestMobileEndpointAccess(TestCase):
    domain = 'test-update-cases'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.request_factory = RequestFactory()
        cls.domain_obj = create_domain(cls.domain)
        initialize_domain_with_default_roles(cls.domain)
        app_editor_role = UserRole.objects.get(name=UserRolePresets.APP_EDITOR)

        cls.web_user = WebUser.create(cls.domain, 'webuser', 'password', None, None,
                                      role_id=app_editor_role.get_id)
        cls.mobile_worker = CommCareUser.create(cls.domain, 'ccuser', 'password', None, None)

    @classmethod
    def tearDownClass(cls):
        cls.domain_obj.delete()
        super().tearDownClass()

    def _make_request(self, user):
        @require_mobile_access
        def my_view(request, domain):
            return HttpResponse()

        request = self.request_factory.get('/myview')
        request.couch_user = user
        request.user = user.get_django_user()
        return my_view(request, self.domain)

    def test_mobile_worker_with_access(self):
        self.assertTrue(self.mobile_worker.has_permission(self.domain, 'access_mobile_endpoints'))
        res = self._make_request(self.mobile_worker)
        self.assertEqual(res.status_code, 200)

    def test_web_user_without_access(self):
        self.assertFalse(self.web_user.has_permission(self.domain, 'access_mobile_endpoints'))
        with self.assertRaises(PermissionDenied):
            self._make_request(self.web_user)
