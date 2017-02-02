"""
UserES
------

Here's an example adapted from the case list report - it gets a list of the ids
of all unknown users, web users, and demo users on a domain.

.. code-block:: python

    from corehq.apps.es import users as user_es

    user_filters = [
        user_es.unknown_users(),
        user_es.web_users(),
        user_es.demo_users(),
    ]

    query = (user_es.UserES()
             .domain(self.domain)
             .OR(*user_filters)
             .show_inactive())

    owner_ids = query.get_ids()
"""
from copy import deepcopy
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
            primary_location,
            location,
            last_logged_in,
        ] + super(UserES, self).builtin_filters

    def show_inactive(self):
        """Include inactive users, which would normally be filtered out."""
        return self.remove_default_filter('active')

    def show_only_inactive(self):
        query = deepcopy(self)
        query._default_filters['active'] = {"term": {"is_active": False}}
        return query

    def users_at_locations_and_descendants(self, location_ids):
        from corehq.apps.locations.models import SQLLocation
        location_ids = SQLLocation.objects.get_locations_and_children_ids(location_ids)
        return self.location(location_ids)

    def users_at_locations(self, location_ids):
        return self.location(location_ids)

    def users_at_accessible_locations(self, domain_name, user):
        from corehq.apps.locations.models import SQLLocation
        accessible_location_ids = SQLLocation.active_objects.accessible_location_ids(domain_name, user)
        return self.users_at_locations(accessible_location_ids)


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
    """
    Return only UnknownUsers.  Unknown users are mock users created from xform
    submissions with unknown user ids.
    """
    return filters.doc_type("UnknownUser")


def admin_users():
    """
    Return only AdminUsers.  Admin users are mock users created from xform
    submissions with unknown user ids whose username is "admin".
    """
    return filters.doc_type("AdminUser")


def demo_users():
    """Matches users whose username is demo_user"""
    return username("demo_user")


def created(gt=None, gte=None, lt=None, lte=None):
    return filters.date_range('created_on', gt, gte, lt, lte)


def last_logged_in(gt=None, gte=None, lt=None, lte=None):
    return filters.date_range('last_login', gt, gte, lt, lte)


def user_ids(user_ids):
    return filters.term("_id", list(user_ids))


def primary_location(location_id):
    # by primary location
    return filters.OR(
        filters.AND(mobile_users(), filters.term('location_id', location_id)),
        filters.AND(
            web_users(),
            filters.term('domain_memberships.location_id', location_id)
        ),
    )


def location(location_id):
    # by any assigned-location primary or not
    return filters.OR(
        filters.AND(mobile_users(), filters.term('assigned_location_ids', location_id)),
        filters.AND(
            web_users(),
            filters.term('domain_memberships.assigned_location_ids', location_id)
        ),
    )


def user_ids_at_locations_and_descendants(location_ids):
    return UserES().users_at_locations_and_descendants(location_ids).exclude_source().run().hits


def user_ids_at_locations(location_ids):
    return UserES().users_at_locations(location_ids).exclude_source().run().hits

def user_ids_at_accessible_locations(domain_name, user):
    return UserES().users_at_accessible_locations(domain_name, user).exclude_source().run().hits
