from __future__ import absolute_import
from __future__ import unicode_literals
import sys

if "django.conf" not in sys.modules:
    # configure django settings for `nosetests corehq/blobs` (run tests fast)
    from django.conf import settings
    settings.configure(
        UNIT_TESTING=True,
        SECRET_KEY="secret",
        SHARED_DRIVE_CONF=None,
        SKIP_TESTS_REQUIRING_EXTRA_SETUP=True,
    )
