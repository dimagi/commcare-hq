from django.http.request import HttpRequest
from django.test import SimpleTestCase

from unittest.mock import patch

from corehq.apps.domain.auth import user_can_access_domain_specific_pages
from corehq.apps.domain.models import Domain
from corehq.apps.users.models import CouchUser


class TestUserCanAccessDomainSpecificPages(SimpleTestCase):
    def test_request_with_no_logged_in_user(self, *args):
        request = HttpRequest()

        with patch('corehq.apps.domain.decorators.active_user_logged_in', return_value=False):
            self.assertFalse(user_can_access_domain_specific_pages(request))

    @patch('corehq.apps.domain.decorators.active_user_logged_in', return_value=True)
    def test_request_with_no_project(self, *args):
        request = HttpRequest()

        with patch('corehq.apps.domain.decorators._ensure_request_project', return_value=None):
            self.assertFalse(user_can_access_domain_specific_pages(request))

    @patch('corehq.apps.domain.decorators.active_user_logged_in', return_value=True)
    def test_request_with_inactive_project(self, *args):
        request = HttpRequest()
        project = Domain(is_active=False)

        with patch('corehq.apps.domain.decorators._ensure_request_project', return_value=project):
            self.assertFalse(user_can_access_domain_specific_pages(request))

    @patch('corehq.apps.domain.decorators.active_user_logged_in', return_value=True)
    @patch('corehq.apps.domain.decorators._ensure_request_project', return_value=Domain(is_active=True))
    def test_request_with_no_couch_user(self, *args):
        request = HttpRequest()

        self.assertFalse(user_can_access_domain_specific_pages(request))

    @patch('corehq.apps.domain.decorators.active_user_logged_in', return_value=True)
    @patch('corehq.apps.domain.decorators._ensure_request_project', return_value=Domain(is_active=True))
    @patch('corehq.apps.domain.decorators._ensure_request_couch_user', return_value=CouchUser())
    def test_request_for_missing_domain_membership_for_non_superuser(self, *args):
        request = HttpRequest()

        self.assertFalse(user_can_access_domain_specific_pages(request))

    @patch('corehq.apps.domain.decorators.active_user_logged_in', return_value=True)
    @patch('corehq.apps.domain.decorators._ensure_request_project', return_value=Domain(is_active=True))
    def test_request_for_missing_domain_membership_for_superuser(self, *args):
        request = HttpRequest()

        couch_user = CouchUser()
        couch_user.is_superuser = True

        with patch('corehq.apps.domain.decorators._ensure_request_couch_user', return_value=couch_user):
            self.assertTrue(user_can_access_domain_specific_pages(request))

    @patch('corehq.apps.domain.decorators.active_user_logged_in', return_value=True)
    @patch('corehq.apps.domain.decorators._ensure_request_project', return_value=Domain(is_active=True))
    @patch('corehq.apps.domain.decorators._ensure_request_couch_user', return_value=CouchUser())
    def test_request_for_valid_domain_membership_for_non_superuser(self, *args):
        request = HttpRequest()

        with patch('corehq.apps.users.models.CouchUser.is_member_of', return_value=True):
            self.assertTrue(user_can_access_domain_specific_pages(request))
