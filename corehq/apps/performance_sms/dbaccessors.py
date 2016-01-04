from corehq.apps.domain.dbaccessors import get_docs_in_domain_by_class
from corehq.apps.performance_sms.models import PerformanceConfiguration
from corehq.dbaccessors.couchapps.all_docs import delete_all_docs_by_doc_type
from corehq.util.test_utils import unit_testing_only


def by_domain(domain):
    return get_docs_in_domain_by_class(domain, PerformanceConfiguration)


def by_interval(interval_keys):
    return list(PerformanceConfiguration.view(
        'performance_sms/by_schedule',
        key=interval_keys,
        reduce=False,
        include_docs=True,
    ))


@unit_testing_only
def delete_all_configs():
    delete_all_docs_by_doc_type(PerformanceConfiguration.get_db(), ('PerformanceConfiguration',))
