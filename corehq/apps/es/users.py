from .es_query import HQESQuery
from . import filters


class UserES(HQESQuery):
    index = 'users'
    default_filters = {
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


def domain(domain):
    return filters.OR(
        filters.term("domain.exact", domain),
        filters.term("domain_memberships.domain.exact", domain)
    )

def username(username):
    return filters.term("username.exact", username)

def web_users():
    return filters.doc_type("WebUser")

def mobile_users():
    return filters.doc_type("CommCareUser")

def unknown_users():
    return filters.doc_type("UnknownUser")

def admin_users():
    return filters.doc_type("AdminUser")

def demo_users():
    return username("demo_user")
