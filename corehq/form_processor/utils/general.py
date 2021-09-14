from django.conf import settings

from corehq.toggles import TF_DOES_NOT_USE_SQLITE_BACKEND


def should_use_sql_backend(domain_object_or_name):
    if settings.ENTERPRISE_MODE or settings.UNIT_TESTING:
        return True
    domain_name, domain_object = _get_domain_name_and_object(domain_object_or_name)
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


def use_sqlite_backend(domain_name):
    return not TF_DOES_NOT_USE_SQLITE_BACKEND.enabled(domain_name) or should_use_sql_backend(domain_name)


def is_commcarecase(obj):
    from casexml.apps.case.models import CommCareCase
    from corehq.form_processor.models import CommCareCaseSQL
    return isinstance(obj, (CommCareCase, CommCareCaseSQL))
