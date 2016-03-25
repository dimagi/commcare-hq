from django.core.urlresolvers import reverse
from corehq.apps.domain.tests.test_views import BaseAutocompleteTest


class TestEmailAuthenticationFormAutocomplete(BaseAutocompleteTest):

    def test_autocomplete_enabled(self):
        self.verify(True, reverse("login"), "auth-username")

    def test_autocomplete_disabled(self):
        self.verify(False, reverse("login"), "auth-username")
