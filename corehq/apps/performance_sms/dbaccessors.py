from django.conf import settings

from corehq.apps.domain.dbaccessors import get_docs_in_domain_by_class
from corehq.apps.domain.models import Domain
from corehq.apps.performance_sms.models import PerformanceConfiguration


def by_domain(domain):
    return list(get_docs_in_domain_by_class(domain, PerformanceConfiguration))


def by_interval(interval_keys):
    return list(PerformanceConfiguration.view(
        'performance_sms/by_schedule',
        key=interval_keys,
        reduce=False,
        include_docs=True,
    ))


def delete_all_configs():
    assert settings.UNIT_TESTING
    db = PerformanceConfiguration.get_db()

    # Since this is a unit test, number of domains is small
    all_domains = Domain.get_all()
    for domain in all_domains:
        domain_configs = by_domain(domain)
        db.bulk_delete(domain_configs)
