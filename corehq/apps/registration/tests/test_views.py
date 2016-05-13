from django.core.urlresolvers import reverse
from corehq.apps.domain.tests.test_views import BaseAutocompleteTest


class TestNewWebUserRegistrationFormAutocomplete(BaseAutocompleteTest):

    def test_autocomplete_enabled(self):
        self.verify(True, reverse("register_user"), "full_name", "email")

    def test_autocomplete_disabled(self):
        self.verify(False, reverse("register_user"), "full_name", "email")
