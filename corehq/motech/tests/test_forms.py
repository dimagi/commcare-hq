from django.test import SimpleTestCase

from ..forms import ConnectionSettingsForm, UnrecognizedHost

from corehq.util.urlvalidate.test.mockipinfo import hostname_resolving_to_ips, unresolvable_hostname


class ConnectionSettingsFormTests(SimpleTestCase):
    def create_form(self, url=None):
        form_data = {
            'name': 'testform',
            'notify_addresses_str': 'test@user.com',
            'url': 'http://some.url'
        }

        if url:
            form_data['url'] = url

        return ConnectionSettingsForm('test_domain', form_data)

    def test_normal_host_is_not_labelled_unreachable(self):
        form = self.create_form(url='http://www.commcarehq.org')

        with hostname_resolving_to_ips('www.commcarehq.org', ['75.2.106.21']):
            self.assertTrue(form.is_valid())
        self.assertNotIsInstance(form.cleaned_data['url'], UnrecognizedHost)

    def test_unreachable_host_is_wrapped_as_valid(self):
        form = self.create_form(url='http://unreachableurl')

        with unresolvable_hostname('unreachableurl'):
            self.assertTrue(form.is_valid())
        self.assertIsInstance(form.cleaned_data['url'], UnrecognizedHost)

    def test_helper_does_not_change_between_references(self):
        form = self.create_form()
        first_helper = form.helper
        second_helper = form.helper
        self.assertIs(first_helper, second_helper)
