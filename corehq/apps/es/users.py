from .es_query import HQESQuery
from . import filters


def domain(self, domain):
    self.OR(
        filters.term("domain.exact", domain),
        filters.term("domain_memberships.domain.exact", domain)
    )


def show_inactive(self):
    return self.remove_default_filter('active')


class UserES(HQESQuery):
    index = 'users'
    default_filters = {
        'mobile_worker': {"term": {"doc_type": "CommCareUser"}},
        'not_deleted': {"term": {"base_doc": "couchuser"}},
        'active': {"term": {"is_active": True}},
    }
    index_filters = [
        domain,
        show_inactive
    ]
