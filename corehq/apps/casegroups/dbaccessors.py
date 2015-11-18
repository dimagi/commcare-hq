from corehq.apps.casegroups.models import CommCareCaseGroup
from corehq.apps.domain.dbaccessors import (
    get_doc_ids_in_domain_by_class,
    get_docs_in_domain_by_class,
)


def get_case_groups_in_domain(domain, limit=None, skip=None):
    def _get_case_groups_generator(domain_name):
        for case_group in get_docs_in_domain_by_class(domain_name, CommCareCaseGroup):
            yield case_group

    case_groups_generator = _get_case_groups_generator(domain)

    if skip is not None:
        try:
            for _ in range(skip):
                next(case_groups_generator)
        except StopIteration:
            pass

    if limit is not None:
        return list(next(case_groups_generator) for _ in range(limit))
    return list(case_groups_generator)


def get_case_group_meta_in_domain(domain):
    """
    returns a list (id, name) tuples sorted by name

    ideal for creating a user-facing dropdown menu, etc.
    """
    return sorted(
        map(
            lambda case_group: (case_group._id, case_group.name),
            get_docs_in_domain_by_class(domain, CommCareCaseGroup)
        ),
        key=lambda id_name_tuple: id_name_tuple[1]
    )


def get_number_of_case_groups_in_domain(domain):
    return len(get_doc_ids_in_domain_by_class(domain, CommCareCaseGroup))
