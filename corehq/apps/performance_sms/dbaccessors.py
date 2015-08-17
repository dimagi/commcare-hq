from corehq.apps.performance_sms.models import PerformanceConfiguration


def by_domain(domain):
    return list(PerformanceConfiguration.view(
        'performance_sms/by_domain',
        key=domain,
        reduce=False,
        include_docs=True
    ))


def by_interval(interval_keys):
    return list(PerformanceConfiguration.view(
        'performance_sms/all_configs',
        key=interval_keys,
        include_docs=True
    ))
