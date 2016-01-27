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
else:
    from .test_fsdb import *
    from .test_init import *
    from .test_mixin import *
