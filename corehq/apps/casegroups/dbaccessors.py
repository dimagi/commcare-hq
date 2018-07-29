from __future__ import absolute_import
from __future__ import unicode_literals
from corehq.apps.casegroups.models import CommCareCaseGroup
from corehq.apps.domain.dbaccessors import (
    get_doc_ids_in_domain_by_class,
    get_docs_in_domain_by_class,
)
from corehq.util.quickcache import quickcache


@quickcache(['domain'], timeout=60 * 60)
def get_case_groups_in_domain(domain):
    groups = get_docs_in_domain_by_class(domain, CommCareCaseGroup)
    groups = sorted(groups, key=lambda group: group.name.lower())
    return groups


def get_case_group_meta_in_domain(domain):
    return [(group.get_id, group.name) for group in get_case_groups_in_domain(domain)]


def search_case_groups_in_domain(domain, search_string, limit=10):
    count = 0
    for result in get_case_group_meta_in_domain(domain):
        if search_string.lower() in result[1].lower():
            yield result
            count += 1
            if count >= limit:
                return


def get_number_of_case_groups_in_domain(domain):
    return len(get_doc_ids_in_domain_by_class(domain, CommCareCaseGroup))
