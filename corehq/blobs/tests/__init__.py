import os
import sys

if "django.conf" not in sys.modules:
    # configure django settings for `nosetests corehq/blobs` (run tests fast)
    from django.conf import settings
    settings.configure(
        UNIT_TESTING=True,
        SECRET_KEY="secret",
    )
else:
    from .test_fsdb import *
    from .test_mixin import *
