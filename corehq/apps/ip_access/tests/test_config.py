from unittest.mock import patch
from django.test import SimpleTestCase

import pytest

from no_exceptions.exceptions import Http403

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
        with self.assertRaises(Http403):
            config.is_allowed(IP_ADDRESS)
