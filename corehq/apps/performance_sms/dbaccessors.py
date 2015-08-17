from django.conf import settings
from corehq.apps.performance_sms.models import PerformanceConfiguration
from dimagi.utils.couch.database import iter_bulk_delete


def by_domain(domain):
    return list(PerformanceConfiguration.view(
        'performance_sms/by_domain',
        key=domain,
        reduce=False,
        include_docs=True
    ))


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
    all_docs = [row['doc'] for row in db.view(
        'performance_sms/by_domain',
        reduce=False,
        include_docs=True
    )]
    db.bulk_delete(all_docs)
