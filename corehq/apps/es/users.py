from .es_query import HQESQuery
from . import filters


class UserES(HQESQuery):
    index = 'users'
    default_filters = {
        'mobile_worker': {"term": {"doc_type": "CommCareUser"}},
        'not_deleted': {"term": {"base_doc": "couchuser"}},
        'active': {"term": {"is_active": True}},
    }
    @property
    def builtin_filters(self):
        return [
            domain,
        ] + super(UserES, self).builtin_filters

    def show_inactive(self):
        return self.remove_default_filter('active')


def domain(self, domain):
    filters.OR(
        filters.term("domain.exact", domain),
        filters.term("domain_memberships.domain.exact", domain)
    )
