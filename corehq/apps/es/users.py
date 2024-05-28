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

from . import filters, queries
from .client import ElasticDocumentAdapter, create_document_adapter
from .const import (
    HQ_USERS_INDEX_CANONICAL_NAME,
    HQ_USERS_INDEX_NAME,
    HQ_USERS_SECONDARY_INDEX_NAME,
)
from .es_query import HQESQuery
from .index.settings import IndexSettingsKey


class UserES(HQESQuery):
    index = HQ_USERS_INDEX_CANONICAL_NAME
    default_filters = {
        'not_deleted': filters.term("base_doc", "couchuser"),
        'active': filters.term("is_active", True),
    }

    @property
    def builtin_filters(self):
        return [
            domain,
            domains,
            created,
            mobile_users,
            web_users,
            user_ids,
            location,
            login_as_user,
            last_logged_in,
            analytics_enabled,
            is_practice_user,
            role_id,
            is_active,
            username,
            missing_or_empty_user_data_property,
        ] + super(UserES, self).builtin_filters

    def show_inactive(self):
        """Include inactive users, which would normally be filtered out."""
        return self.remove_default_filter('active')

    def show_only_inactive(self):
        query = self.remove_default_filter('active')
        return query.is_active(False)


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


def domain(domain, allow_enterprise=False):
    domain_list = [domain]
    if allow_enterprise:
        from corehq.apps.enterprise.models import EnterprisePermissions
        config = EnterprisePermissions.get_by_domain(domain)
        if config.is_enabled and domain in config.domains:
            domain_list.append(config.source_domain)
    return domains(domain_list)


def domains(domains):
    return filters.OR(
        filters.term("domain.exact", domains),
        filters.term("domain_memberships.domain.exact", domains)
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
    """Matches users whose username is demo_user"""
    return username("demo_user")


def created(gt=None, gte=None, lt=None, lte=None):
    return filters.date_range('created_on', gt, gte, lt, lte)


def last_logged_in(gt=None, gte=None, lt=None, lte=None):
    return filters.date_range('last_login', gt, gte, lt, lte)


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


def role_id(role_id):
    return filters.OR(
        filters.term("domain_membership.role_id", role_id),     # mobile users
        filters.term("domain_memberships.role_id", role_id)     # web users
    )


def is_active(active=True):
    return filters.term("is_active", active)


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
    return _user_data(key, queries.match(field='user_data_es.value', search_string=value))


def login_as_user(value):
    return _user_data('login_as_user', filters.term('user_data_es.value', value))


def missing_or_empty_user_data_property(property_name):
    """
    A user_data property doesn't exist, or does exist but has an empty string value.
    """
    missing_property = filters.NOT(queries.nested(
        'user_data_es',
        filters.term(field='user_data_es.key', value=property_name),
    ))
    empty_value = _user_data(property_name, filters.term('user_data_es.value', ''))
    return filters.OR(missing_property, empty_value)
