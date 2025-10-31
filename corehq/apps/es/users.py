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
             .OR(*user_filters))

    owner_ids = query.get_ids()
"""

from . import filters, queries
from .client import ElasticDocumentAdapter, create_document_adapter
from .const import (
    HQ_USERS_INDEX_CANONICAL_NAME,
    HQ_USERS_INDEX_NAME,
    HQ_USERS_SECONDARY_INDEX_NAME,
)
from .es_query import HQESQuery
from .utils import get_user_domain_memberships
from .index.settings import IndexSettingsKey


class UserES(HQESQuery):
    index = HQ_USERS_INDEX_CANONICAL_NAME
    default_filters = {
        'not_deleted': filters.term("base_doc", "couchuser"),
    }

    @property
    def builtin_filters(self):
        return [
            domain,
            active_on_any_domain,
            created,
            mobile_users,
            web_users,
            exclude_dimagi_users,
            user_ids,
            location,
            login_as_user,
            last_logged_in,
            last_modified,
            analytics_enabled,
            is_practice_user,
            is_admin,
            role_id,
            is_active,
            is_inactive,
            account_confirmed,
            username,
            missing_or_empty_user_data_property,
        ] + super(UserES, self).builtin_filters


class ElasticUser(ElasticDocumentAdapter):

    settings_key = IndexSettingsKey.USERS
    canonical_name = HQ_USERS_INDEX_CANONICAL_NAME

    @property
    def model_cls(self):
        from corehq.apps.users.models import CouchUser
        return CouchUser

    @property
    def mapping(self):
        from .mappings.user_mapping import USER_MAPPING
        return USER_MAPPING

    def _from_dict(self, user_dict):
        """
        Takes a user dict and applies required transfomation to make it suitable for ES.

        :param user: an instance ``dict`` which is result of ``CouchUser.to_json()``
        """
        from corehq.apps.groups.dbaccessors import (
            get_group_id_name_map_by_user,
        )

        if user_dict['doc_type'] == 'CommCareUser' and '@' in user_dict['username']:
            user_dict['base_username'] = user_dict['username'].split("@")[0]
        else:
            user_dict['base_username'] = user_dict['username']

        results = get_group_id_name_map_by_user(user_dict['_id'])
        user_dict['__group_ids'] = [res.id for res in results]
        user_dict['__group_names'] = [res.name for res in results]
        user_dict['user_data_es'] = []
        user_dict.pop('password', None)

        memberships = get_user_domain_memberships(user_dict)
        user_dict['user_domain_memberships'] = memberships

        if user_dict.get('base_doc') == 'CouchUser' and user_dict['doc_type'] == 'CommCareUser':
            user_obj = self.model_cls.wrap_correctly(user_dict)
            user_data = user_obj.get_user_data(user_obj.domain)
            for key, value in user_data.items():
                user_dict['user_data_es'].append({
                    'key': key,
                    'value': value,
                })
        return super()._from_dict(user_dict)


user_adapter = create_document_adapter(
    ElasticUser,
    HQ_USERS_INDEX_NAME,
    "user",
    secondary=HQ_USERS_SECONDARY_INDEX_NAME,
)


def domain(domain, *, include_active=True, include_inactive=False):
    domains = [domain] if isinstance(domain, str) else domain
    domain_filter = filters.OR(
        filters.term("domain.exact", domains),
        filters.nested(
            'user_domain_memberships',
            filters.term('user_domain_memberships.domain.exact', domains),
        )
    )

    if include_active and include_inactive:  # all
        return domain_filter
    if include_active and not include_inactive:  # only active
        return filters.AND(
            domain_filter,
            is_active(domain),
        )
    if not include_active and include_inactive:  # only inactive
        return filters.AND(
            domain_filter,
            is_inactive(domain),
        )
    return filters.match_none()


def is_active(domain):
    return filters.AND(
        filters.term("is_active", True),
        filters.nested('user_domain_memberships', filters.AND(
            filters.term('user_domain_memberships.domain.exact', domain),
            filters.NOT(filters.term('user_domain_memberships.is_active', False)),
        ))
    )


def is_inactive(domain):
    return filters.OR(
        filters.term("is_active", False),
        filters.nested('user_domain_memberships', filters.AND(
            filters.term('user_domain_memberships.domain.exact', domain),
            filters.term('user_domain_memberships.is_active', False),
        ))
    )


def account_confirmed(is_confirmed=False):
    return filters.term("is_account_confirmed", is_confirmed)


def active_on_any_domain():
    return filters.AND(
        filters.term("is_active", True),
        filters.nested('user_domain_memberships', filters.AND(
            filters.term('user_domain_memberships.is_active', True)
        ))
    )


def analytics_enabled(enabled=True):
    if enabled:
        return filters.OR(
            filters.term("analytics_enabled", True),
            filters.missing("analytics_enabled")
        )
    else:
        return filters.term("analytics_enabled", False)


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
    """Matches users who has is_demo_user set to True"""
    return filters.term("is_demo_user", True)


def exclude_dimagi_users():
    """Exclude users whose username ends with @dimagi.com"""
    return filters.NOT(filters.wildcard("username.exact", "*@dimagi.com"))


def created(gt=None, gte=None, lt=None, lte=None):
    return filters.date_range('created_on', gt, gte, lt, lte)


def last_logged_in(gt=None, gte=None, lt=None, lte=None):
    return filters.date_range('last_login', gt, gte, lt, lte)


def last_modified(gt=None, gte=None, lt=None, lte=None):
    return filters.date_range('last_modified', gt, gte, lt, lte)


def user_ids(user_ids):
    return filters.term("_id", list(user_ids))


def location(location_id):
    # by any assigned-location primary or not
    return filters.OR(
        filters.AND(mobile_users(), filters.term('assigned_location_ids', location_id)),
        filters.AND(
            web_users(),
            filters.term('domain_memberships.assigned_location_ids', location_id)
        ),
    )


def is_practice_user(practice_mode=True):
    return filters.term('is_demo_user', practice_mode)


def is_admin(domain):
    return filters.nested(
        'user_domain_memberships',
        filters.AND(
            filters.term('user_domain_memberships.domain.exact', domain),
            filters.term('user_domain_memberships.is_admin', True),
        )
    )


def role_id(role_id):
    return filters.OR(
        filters.term("domain_membership.role_id", role_id),     # mobile users
        filters.term("domain_memberships.role_id", role_id)     # web users
    )


def _user_data(key, filter_):
    # Note: user data does not exist in ES for web users
    return queries.nested(
        'user_data_es',
        filters.AND(
            filters.term(field='user_data_es.key', value=key),
            filter_
        )
    )


def query_user_data(key, value):
    if value is None:
        return filters.match_none()
    return _user_data(key, queries.match(field='user_data_es.value', search_string=value))


def login_as_user(value):
    return _user_data('login_as_user', filters.term('user_data_es.value', value))


def _missing_user_data_property(property_name):
    """
    A user_data property doesn't exist.
    """
    return filters.NOT(queries.nested(
        'user_data_es',
        filters.term(field='user_data_es.key', value=property_name),
    ))


def _empty_user_data_property(property_name):
    """
    A user_data property exists but has an empty string value.
    """
    return _user_data(
        property_name,
        filters.NOT(
            filters.wildcard(field='user_data_es.value', value='*')
        )
    )


def missing_or_empty_user_data_property(property_name):
    """
    A user_data property doesn't exist, or does exist but has an empty string value.
    """
    return filters.OR(
        _missing_user_data_property(property_name),
        _empty_user_data_property(property_name),
    )


def iter_web_user_emails(domain_name):
    return (
        hit['email'] or hit['username']
        for hit in (
            UserES()
            .domain(domain_name)
            .web_users()
            .fields(('email', 'username'))
            .scroll()
        )
    )
