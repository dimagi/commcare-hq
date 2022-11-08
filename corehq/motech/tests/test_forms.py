from django.test import SimpleTestCase

from corehq.util.urlvalidate.test.mockipinfo import (
    hostname_resolving_to_ips,
    unresolvable_hostname,
)

from ..forms import ConnectionSettingsForm, UnrecognizedHost


class ConnectionSettingsFormTests(SimpleTestCase):

    def create_form(self, url=None, notify_emails='test@user.com'):
        form_data = {
            'name': 'testform',
            'notify_addresses_str': notify_emails,
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

    def test_clean_notify_addresses_str(self):
        email_addrs = "test1@user.com, test2@user.com"
        form = self.create_form(notify_emails=email_addrs)
        self.assertTrue(form.is_valid())
        self.assertEqual(email_addrs, form.cleaned_data["notify_addresses_str"])

    def test_clean_notify_addresses_str_validation_error(self):
        for bad_addr in ["invalid&example.com", "<test@example.com>"]:
            email_addrs = f"valid@example.com, {bad_addr}"
            form = self.create_form(notify_emails=email_addrs)
            self.assertEqual(
                {"notify_addresses_str": [{
                    "message": f"Invalid email address(es): {bad_addr}",
                    "code": "",
                }]},
                form.errors.get_json_data(),
            )
