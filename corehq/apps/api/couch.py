from corehq.apps.domain.dbaccessors import get_doc_count_in_domain_by_class, \
    get_docs_in_domain_by_class
from corehq.apps.groups.models import Group
from corehq.apps.users.analytics import (
    get_active_commcare_users_in_domain,
    get_count_of_active_commcare_users_in_domain,
    get_count_of_inactive_commcare_users_in_domain,
    get_inactive_commcare_users_in_domain,
)


class UserQuerySetAdapter(object):

    def __init__(self, domain, show_archived):
        self.domain = domain
        self.show_archived = show_archived

    def count(self):
        if self.show_archived:
            return get_count_of_inactive_commcare_users_in_domain(self.domain)
        else:
            return get_count_of_active_commcare_users_in_domain(self.domain)

    def __getitem__(self, item):
        if isinstance(item, slice):
            limit = item.stop - item.start
            if self.show_archived:
                return get_inactive_commcare_users_in_domain(self.domain, start_at=item.start, limit=limit)
            else:
                return get_active_commcare_users_in_domain(self.domain, start_at=item.start, limit=limit)
        raise ValueError(
            'Invalid type of argument. Item should be an instance of slice class.')


class GroupQuerySetAdapter(object):
    def __init__(self, domain):
        self.domain = domain

    def count(self):
        return get_doc_count_in_domain_by_class(self.domain, Group)

    def __getitem__(self, item):
        if isinstance(item, slice):
            limit = item.stop - item.start
            return get_docs_in_domain_by_class(self.domain, Group, limit=limit, skip=item.start)
        raise ValueError(
            'Invalid type of argument. Item should be an instance of slice class.')
