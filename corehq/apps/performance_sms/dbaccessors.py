from corehq.apps.performance_sms.models import PerformanceConfiguration


def by_domain(domain):
    return list(PerformanceConfiguration.view('performance_sms/by_domain', key=domain, include_docs=True))
