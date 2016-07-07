from mock import patch
from django.core.urlresolvers import reverse
from corehq.apps.analytics.ab_tests import NEW_USER_SIGNUP_OPTION_OLD
from corehq.apps.domain.tests.test_views import BaseAutocompleteTest


class TestNewWebUserRegistrationFormAutocomplete(BaseAutocompleteTest):

    def test_autocomplete_enabled(self):
        with patch('corehq.apps.registration.views.ab_tests.ABTest.version', NEW_USER_SIGNUP_OPTION_OLD):
            self.verify(True, reverse("register_user"), "full_name", "email")

    def test_autocomplete_disabled(self):
        with patch('corehq.apps.registration.views.ab_tests.ABTest.version', NEW_USER_SIGNUP_OPTION_OLD):
            self.verify(False, reverse("register_user"), "full_name", "email")
