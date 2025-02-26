from unittest.mock import patch

from django.conf import settings

from corehq.project_limits.models import SystemLimit

_systemlimit_domainlimit_patch = patch.object(SystemLimit, "_cache_domain_specific_limit")


def patch_systemlimit_cache():
    assert settings.UNIT_TESTING
    SystemLimit._get_global_limit = SystemLimit._get_global_limit.__wrapped__
    # Use __enter__ and __exit__ to start/stop so patch.stopall() does not stop it.
    _systemlimit_domainlimit_patch.__enter__()
