from django.conf import settings

from corehq.apps.domain.models import Domain
from corehq.toggles import USE_SQL_BACKEND


def should_use_sql_backend(domain):
    if settings.UNIT_TESTING:
        override = getattr(settings, 'TESTS_SHOULD_USE_SQL_BACKEND', None)
        if override is not None:
            return override

    return USE_SQL_BACKEND.enabled(domain) or Domain.get_by_name(domain).use_sql_backend


def is_commcarecase(obj):
    from casexml.apps.case.models import CommCareCase
    from corehq.form_processor.models import CommCareCaseSQL
    return isinstance(obj, (CommCareCase, CommCareCaseSQL))
