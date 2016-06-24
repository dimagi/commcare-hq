from django.conf import settings

from corehq.toggles import USE_SQL_BACKEND, NAMESPACE_DOMAIN, NEW_EXPORTS
from dimagi.utils.logging import notify_exception


def should_use_sql_backend(domain_name):
    from corehq.apps.domain.models import Domain
    if settings.UNIT_TESTING:
        return _should_use_sql_backend_in_tests(domain_name)

    # TODO: remove toggle once all domains have been migrated
    toggle_enabled = USE_SQL_BACKEND.enabled(domain_name)
    if toggle_enabled:
        try:
            # migrate domains in toggle
            domain = Domain.get_by_name(domain_name)
            if not domain.use_sql_backend:
                domain.use_sql_backend = True
                domain.save()
                USE_SQL_BACKEND.set(domain_name, enabled=False, namespace=NAMESPACE_DOMAIN)
        except Exception:
            notify_exception(None, "Error migrating SQL BACKEND toggle", {
                'domain': domain_name
            })
        return True

    return toggle_enabled or Domain.get_by_name(domain_name).use_sql_backend


def _should_use_sql_backend_in_tests(domain_name):
    """The default return value is False unless the ``TESTS_SHOULD_USE_SQL_BACKEND`` setting
    has been set or a Domain object with the same name exists."""
    assert settings.UNIT_TESTING
    from corehq.apps.domain.models import Domain
    override = getattr(settings, 'TESTS_SHOULD_USE_SQL_BACKEND', None)
    if override is not None:
        return override
    elif getattr(settings, 'DB_ENABLED', True):
        domain = Domain.get_by_name(domain_name)
        return domain and domain.use_sql_backend
    else:
        return False


def use_new_exports(domain_name):
    return NEW_EXPORTS.enabled(domain_name) or should_use_sql_backend(domain_name)


def is_commcarecase(obj):
    from casexml.apps.case.models import CommCareCase
    from corehq.form_processor.models import CommCareCaseSQL
    return isinstance(obj, (CommCareCase, CommCareCaseSQL))
