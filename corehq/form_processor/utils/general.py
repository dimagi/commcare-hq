from __future__ import absolute_import
from __future__ import unicode_literals
import threading

from django.conf import settings

from corehq.toggles import OLD_EXPORTS, TF_DOES_NOT_USE_SQLITE_BACKEND

_thread_local = threading.local()


def get_local_domain_sql_backend_override(domain):
    try:
        return _thread_local.use_sql_backend[domain]
    except (AttributeError, KeyError):
        return None


def set_local_domain_sql_backend_override(domain):
    use_sql_backend_dict = getattr(_thread_local, 'use_sql_backend', {})
    use_sql_backend_dict[domain] = True
    _thread_local.use_sql_backend = use_sql_backend_dict


def clear_local_domain_sql_backend_override(domain):
    use_sql_backend_dict = getattr(_thread_local, 'use_sql_backend', {})
    use_sql_backend_dict.pop(domain, None)
    _thread_local.use_sql_backend = use_sql_backend_dict


def should_use_sql_backend(domain_object_or_name):
    if settings.ENTERPRISE_MODE:
        return True
    domain_name, domain_object = _get_domain_name_and_object(domain_object_or_name)
    local_override = get_local_domain_sql_backend_override(domain_name)
    if local_override is not None:
        return local_override

    if settings.UNIT_TESTING:
        return _should_use_sql_backend_in_tests(domain_object)

    return domain_object and domain_object.use_sql_backend


def _should_use_sql_backend_in_tests(domain_object):
    """The default return value is False unless the ``TESTS_SHOULD_USE_SQL_BACKEND`` setting
    has been set or a Domain object with the same name exists."""
    assert settings.UNIT_TESTING
    override = getattr(settings, 'TESTS_SHOULD_USE_SQL_BACKEND', None)
    if override is not None:
        return override

    return domain_object and domain_object.use_sql_backend


def _get_domain_name_and_object(domain_object_or_name):
    from corehq.apps.domain.models import Domain
    if domain_object_or_name is None:
        return None, None
    elif isinstance(domain_object_or_name, Domain):
        return domain_object_or_name.name, domain_object_or_name
    elif getattr(settings, 'DB_ENABLED', True):
        return domain_object_or_name, Domain.get_by_name(domain_object_or_name)
    else:
        return domain_object_or_name, None


def use_new_exports(domain_name):
    return (not OLD_EXPORTS.enabled(domain_name)) or should_use_sql_backend(domain_name)


def use_sqlite_backend(domain_name):
    return not TF_DOES_NOT_USE_SQLITE_BACKEND.enabled(domain_name) or should_use_sql_backend(domain_name)


def is_commcarecase(obj):
    from casexml.apps.case.models import CommCareCase
    from corehq.form_processor.models import CommCareCaseSQL
    return isinstance(obj, (CommCareCase, CommCareCaseSQL))
