from django.conf import settings

from corehq.toggles import USE_SQL_BACKEND


def should_use_sql_backend(domain):
    if settings.UNIT_TESTING:
        override = getattr(settings, 'TESTS_SHOULD_USE_SQL_BACKEND', None)
        if override is not None:
            return override

    return USE_SQL_BACKEND.enabled(domain)
