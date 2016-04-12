from corehq.apps.domain.models import Domain
from corehq.util.test_utils import unit_testing_only


@unit_testing_only
def delete_all_domains():
    domains = list(Domain.get_all())
    Domain.bulk_delete(domains)
