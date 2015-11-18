from corehq.apps.domain.dbaccessors import (
    get_docs_in_domain_by_class,
    get_doc_ids_in_domain_by_class,
)


def group_by_domain(domain):
    from corehq.apps.groups.models import Group
    return get_docs_in_domain_by_class(domain, Group)


def group_by_name(domain, name, include_docs=True):
    return filter(
        lambda group: group.name == name,
        group_by_domain(domain)
    )


def get_group_ids_by_domain(domain):
    from corehq.apps.groups.models import Group
    return get_doc_ids_in_domain_by_class(domain, Group)
