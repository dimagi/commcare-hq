from django.test import SimpleTestCase

from ..forms import ConnectionSettingsForm, UnrecognizedHost

from corehq.util.urlsanitize.test.mockipinfo import hostname_resolving_to_ips, unresolvable_hostname

import time


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
        start = time.time()
        form = self.create_form(url='http://www.commcarehq.org')
        end = time.time()
        print(f'form Creation in {end - start}')

        start = time.time()
        with hostname_resolving_to_ips('www.commcarehq.org', ['75.2.106.21']):
            self.assertTrue(form.is_valid())
        self.assertNotIsInstance(form.cleaned_data['url'], UnrecognizedHost)
        end = time.time()
        print(f'Everythign else in {end - start}')

    def test_unreachable_host_is_wrapped_as_valid(self):
        form = self.create_form(url='http://unreachableurl')

        with unresolvable_hostname('unreachableurl'):
            self.assertTrue(form.is_valid())
        self.assertIsInstance(form.cleaned_data['url'], UnrecognizedHost)
