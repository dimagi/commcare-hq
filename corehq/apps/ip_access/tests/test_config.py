import pytest

from unittest.mock import patch
from django.test import SimpleTestCase

from corehq.apps.domain.forms import IPAccessConfigForm
from ..models import IPAccessConfig

IP_ADDRESS = '192.0.2.10'
IP_COUNTRY = 'US'
IP_OTHER_COUNTRY = 'CA'
DOMAIN = 'test-ip-access'


@pytest.mark.parametrize("countries, allowlist, denylist, expected", [
    # Country allowed
    ([IP_COUNTRY], [], [], True),
    ([IP_COUNTRY], [IP_ADDRESS], [], True),
    ([IP_COUNTRY], [], [IP_ADDRESS], False),

    # Country not allowed
    ([IP_OTHER_COUNTRY], [], [], False),
    ([IP_OTHER_COUNTRY], [IP_ADDRESS], [], True),
    ([IP_OTHER_COUNTRY], [], [IP_ADDRESS], False),

    # No country specified (all allowed)
    ([], [], [], True),
    ([], [IP_ADDRESS], [], True),  # No need to allowlist without country-level
                                   # restrictions, but this should work anyways
    ([], [], [IP_ADDRESS], False),
])
@patch('django.conf.settings.MAXMIND_LICENSE_KEY', 'TEST')
def test_is_allowed(countries, allowlist, denylist, expected):
    config = IPAccessConfig(
        domain=DOMAIN,
        country_allowlist=countries,
        ip_allowlist=allowlist,
        ip_denylist=denylist,
    )
    with patch('corehq.apps.ip_access.models.get_ip_country', return_value=IP_COUNTRY):
        assert config.is_allowed(IP_ADDRESS) is expected


class NoLicenseTests(SimpleTestCase):
    def test_is_allowed_no_license_with_country_list(self):
        config = IPAccessConfig(
            domain=DOMAIN,
            country_allowlist=[IP_COUNTRY],
            ip_allowlist=[],
            ip_denylist=[],
        )
        with self.assertRaises(Exception):
            config.is_allowed(IP_ADDRESS)


class IPAccessConfigFormTests(SimpleTestCase):
    def test_cant_submit_country_without_license(self):
        post_data = self._create_form_input(country_allowlist=[IP_COUNTRY])
        form = IPAccessConfigForm(post_data, current_ip=IP_ADDRESS, current_country=None)
        self.assertFalse(form.is_valid())

    def test_cant_submit_same_ip_in_both_lists(self):
        post_data = self._create_form_input(ip_allowlist=IP_ADDRESS, ip_denylist=IP_ADDRESS)
        form = IPAccessConfigForm(post_data, current_ip=IP_ADDRESS, current_country=None)
        self.assertFalse(form.is_valid())

    @patch('django.conf.settings.MAXMIND_LICENSE_KEY', 'TEST')
    def test_cant_lock_out_self(self):
        post_data = self._create_form_input(country_allowlist=[IP_OTHER_COUNTRY])
        form = IPAccessConfigForm(post_data, current_ip=IP_ADDRESS, current_country=IP_COUNTRY)
        self.assertFalse(form.is_valid())

        # You can exclude your country only if you include your IP address in the allow list
        post_data = self._create_form_input(country_allowlist=[IP_OTHER_COUNTRY], ip_allowlist=IP_ADDRESS)
        form = IPAccessConfigForm(post_data, current_ip=IP_ADDRESS, current_country=IP_COUNTRY)
        self.assertTrue(form.is_valid())

        post_data = self._create_form_input(ip_denylist=IP_ADDRESS)
        form = IPAccessConfigForm(post_data, current_ip=IP_ADDRESS, current_country=IP_COUNTRY)
        self.assertFalse(form.is_valid())

    def test_cant_submit_invalid_ip(self):
        post_data = self._create_form_input(ip_denylist='Invalid.IP')
        form = IPAccessConfigForm(post_data, current_ip=IP_ADDRESS, current_country=IP_COUNTRY)
        self.assertFalse(form.is_valid())

    def _create_form_input(self, country_allowlist=None, ip_allowlist=None, ip_denylist=None, comment=None):
        return {
            'country_allowlist': country_allowlist or [],
            'ip_allowlist': ip_allowlist or '',
            'ip_denylist': ip_denylist or '',
            'comment': comment or ''
        }
