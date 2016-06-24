from django.conf import settings

from corehq.toggles import USE_SQL_BACKEND, NAMESPACE_DOMAIN


def should_use_sql_backend(domain_name):
    from corehq.apps.domain.models import Domain
    if settings.UNIT_TESTING:
        override = getattr(settings, 'TESTS_SHOULD_USE_SQL_BACKEND', None)
        if override is not None:
            return override

    toggle_enabled = USE_SQL_BACKEND.enabled(domain_name)
    if toggle_enabled:
        domain = Domain.get_by_name(domain_name)
        if not domain.use_sql_backend:
            domain.use_sql_backend = True
            domain.save()
            USE_SQL_BACKEND.set(domain_name, enabled=False, namespace=NAMESPACE_DOMAIN)
        return True

    return toggle_enabled or Domain.get_by_name(domain_name).use_sql_backend


def is_commcarecase(obj):
    from casexml.apps.case.models import CommCareCase
    from corehq.form_processor.models import CommCareCaseSQL
    return isinstance(obj, (CommCareCase, CommCareCaseSQL))
