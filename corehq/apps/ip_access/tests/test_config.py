from unittest.mock import patch

import pytest

from ..models import IPAccessConfig

IP_ADDRESS = '192.0.2.10'
DOMAIN = 'test-ip-access'


@pytest.mark.parametrize("in_country, allowlist, denylist, expected", [
    (True, [], [], True),
    (True, [IP_ADDRESS], [], True),
    (True, [], [IP_ADDRESS], False),
    (True, [IP_ADDRESS], [IP_ADDRESS], False),  # kinda silly config, but whatever
    (False, [], [], False),
    (False, [IP_ADDRESS], [], True),
    (False, [], [IP_ADDRESS], False),
    (False, [IP_ADDRESS], [IP_ADDRESS], False),  # kinda silly config, but whatever
])
def test_is_allowed(in_country, allowlist, denylist, expected):
    config = IPAccessConfig(
        domain=DOMAIN,
        country_allowlist=[],  # patching this anyways
        ip_allowlist=allowlist,
        ip_denylist=denylist,
    )
    with patch('corehq.apps.ip_access.models.is_in_country') as is_in_country_patch:
        is_in_country_patch.return_value = in_country
        assert config.is_allowed(IP_ADDRESS) is expected
