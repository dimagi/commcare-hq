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


def setUpModule():
    from corehq.elastic import get_es_new, debug_assert
    debug_assert(get_es_new())
