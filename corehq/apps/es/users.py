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
            created,
            mobile_users,
            web_users,
            user_ids,
            location,
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


def created(gt=None, gte=None, lt=None, lte=None):
    return filters.date_range('created_on', gt, gte, lt, lte)


def user_ids(user_ids):
    return filters.term("_id", list(user_ids))


def location(location_id):
    return filters.OR(
        filters.AND(mobile_users(), filters.term('location_id', location_id)),
        filters.AND(
            web_users(),
            filters.term('domain_memberships.location_id', location_id)
        ),
    )
