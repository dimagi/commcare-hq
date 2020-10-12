from unittest import skip # pylint: disable=unused-import
import mock

from django.http import HttpResponse, Http404
from django.test import SimpleTestCase, tag
from django.test.client import RequestFactory
from rest_framework import status

from corehq.apps.domain.decorators import login_and_domain_required
from corehq.apps.domain.models import Domain


@login_and_domain_required
def process_request(*args, **kwargs):
    return HttpResponse('')


@tag('unit')
class TestLoginAndDomainRequired(SimpleTestCase):
    def setUp(self):
        self.domain_name = 'some_domain'
        self.domain = self._create_domain()
        self.factory = RequestFactory()
        self.user = self._create_user()
        self.request = self._create_request('/some/url', self.user)

        self.domain_patcher = mock.patch('corehq.apps.domain.models.Domain.get_by_name', return_value=self.domain)
        self.get_domain_by_name = self.domain_patcher.start()
        self.addCleanup(self.domain_patcher.stop)

    @staticmethod
    def _create_domain():
        domain = mock.Mock(Domain)
        domain.is_active = True
        domain.is_snapshot = False
        return domain

    @staticmethod
    def _create_user():
        user = mock.Mock()
        user.is_superuser = False
        user.is_member_of = mock.Mock(return_value=False)
        return user

    def _create_request(self, url, user):
        request = self.factory.get(url)
        request.user = request.couch_user = user
        request.path = 'access_required.html'
        request.domain = self.domain_name

        return request

    def process_request(self):
        return process_request(self.request, self.domain_name)

    def test_invalid_domain__displays_404(self):
        self.get_domain_by_name.return_value = None

        with self.assertRaises(Http404):
            self.process_request()

    # Reverse is stubbed here because actual reverse lookups take ~ 1 second
    @mock.patch('corehq.apps.domain.decorators.reverse')
    @mock.patch('corehq.apps.domain.decorators.messages', mock.Mock())
    def test_inactive_domain__redirects_to_domain_selection(self, reverse):
        self.domain.is_active = False
        reverse.return_value = '/domain/select/'

        response = self.process_request()
        self.assertEqual(response.status_code, status.HTTP_302_FOUND)
        reverse.assert_called_with('domain_select')

    def test_two_factor_required_but_missing__displays_alert(self):
        self.domain.two_factor_auth = True
        self.user.is_member_of.return_value = True
        self.user.two_factor_disabled = False
        self.user.is_verified = mock.Mock(return_value=False)

        response = self.process_request()
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_snapshot_domain_without_previewer__returns_not_found(self):
        self.domain.is_snapshot = True
        self.user.is_previewer = mock.Mock(return_value=False)
        with self.assertRaises(Http404):
            self.process_request()

    def test_snapshot_domain_with_previewer__allows_access(self):
        self.domain.is_snapshot = True
        self.user.is_previewer = mock.Mock(return_value=True)
        response = self.process_request()
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_user_belongs_to_domain__returns_200(self):
        self.user.is_member_of.return_value = True
        response = self.process_request()
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    @mock.patch('corehq.apps.domain.decorators.has_privilege', mock.Mock(return_value=False))
    @mock.patch('corehq.apps.domain.views.accounting.SubscriptionUpgradeRequiredView')
    def test_domain_user_does_not_have_project_access__renders_subscription_upgrade(self, upgrade_required_view_class):
        self.user.is_member_of.return_value = True
        upgrade_required_view = mock.Mock()
        upgrade_required_view_class.return_value = upgrade_required_view

        with self.settings(IS_SAAS_ENVIRONMENT=True):
            self.process_request()
            upgrade_required_view.get.assert_called()

    @mock.patch('corehq.apps.domain.decorators.has_privilege', mock.Mock(return_value=False))
    def test_domain_user_does_not_have_project_access_but_is_non_saas__allows_access(self):
        with self.settings(IS_SAAS_ENVIRONMENT=False):
            self.user.is_member_of.return_value = True
            response = self.process_request()
            self.assertEqual(response.status_code, status.HTTP_200_OK)

    @mock.patch('corehq.apps.hqwebapp.views.loader.get_template', mock.Mock())
    def test_superuser_when_superusers_restricted__is_forbidden(self):
        self.domain.restrict_superuers = True
        self.user.is_superuser = True

        response = self.process_request()
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    @mock.patch('corehq.apps.hqwebapp.views.loader.get_template', mock.Mock())
    def test_superuser_when_page_is_whitelisted__is_granted_access(self):
        with self.settings(PAGES_NOT_RESTRICTED_FOR_DIMAGI=[self.request.path]):
            self.domain.restrict_superusers = True
            self.user.is_superuser = True

            response = self.process_request()
            self.assertEqual(response.status_code, status.HTTP_200_OK)

    @mock.patch('corehq.apps.users.views.DomainRequestView')
    def test_web_user_where_domain_allows_requests__is_granted_access(self, domain_request_view_class):
        self.user.is_web_user.return_value = True
        self.domain.allow_domain_requests = True
        domain_request_view = mock.Mock()
        domain_request_view_class.as_view.return_value = domain_request_view

        self.process_request()
        domain_request_view.assert_called()

    # Non-domain, non-web user is denied access
    def test_non_domain_user__is_denied_access(self):
        self.user.is_web_user.return_value = False

        with self.assertRaises(Http404):
            self.process_request()
