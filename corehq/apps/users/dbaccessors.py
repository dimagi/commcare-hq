from collections import namedtuple

from dimagi.utils.couch.database import iter_bulk_delete, iter_docs

from corehq.apps.es import UserES
from corehq.apps.es.users import web_users, mobile_users
from corehq.apps.locations.models import SQLLocation
from corehq.apps.users.models import CommCareUser, CouchUser, Invitation, UserRole
from corehq.pillows.utils import MOBILE_USER_TYPE, WEB_USER_TYPE
from corehq.util.couch import stale_ok
from corehq.util.quickcache import quickcache
from corehq.util.test_utils import unit_testing_only

UserExists = namedtuple('UserExists', 'exists is_deleted')


def get_user_id_by_username(username):
    if not username:
        return None

    result = CouchUser.view(
        'users/by_username',
        key=username,
        include_docs=False,
        reduce=False,
        stale=stale_ok(),
    )
    row = result.one()
    if row:
        return row["id"]
    return None


def get_display_name_for_user_id(domain, user_id, default=None):
    if user_id:
        user = CouchUser.get_by_user_id(user_id)
        if user:
            return user.full_name
    return default


def get_user_id_and_doc_type_by_domain(domain):
    key = ['active', domain]
    return [
        {"id": u['id'], "doc_type": u['key'][2]}
        for u in CouchUser.view(
            'users/by_domain',
            reduce=False,
            startkey=key,
            endkey=key + [{}],
            include_docs=False,
        ).all()
    ]


def get_all_commcare_users_by_domain(domain):
    """Returns all CommCareUsers by domain regardless of their active status"""
    ids = get_all_user_ids_by_domain(domain, include_web_users=False)
    return map(CommCareUser.wrap, iter_docs(CommCareUser.get_db(), ids))


def get_all_web_users_by_domain(domain):
    """Returns all WebUsers by domain"""
    from corehq.apps.users.models import WebUser
    ids = get_all_user_ids_by_domain(domain, include_mobile_users=False)
    return map(WebUser.wrap, iter_docs(WebUser.get_db(), ids))


def get_mobile_usernames_by_filters(domain, user_filters):
    query = _get_es_query(domain, MOBILE_USER_TYPE, user_filters)
    return query.values_list('base_username', flat=True)


def _get_es_query(domain, user_type, user_filters):
    role_id = user_filters.get('role_id', None)
    search_string = user_filters.get('search_string', None)
    location_id = user_filters.get('location_id', None)
    # The following two filters applies only to MOBILE_USER_TYPE
    selected_location_only = user_filters.get('selected_location_only', False)
    user_active_status = user_filters.get('user_active_status', None)

    if user_active_status is None:
        # Show all users in domain - will always be true for WEB_USER_TYPE
        query = UserES().domain(domain).remove_default_filter('active')
    elif user_active_status:
        # Active users filtered by default
        query = UserES().domain(domain)
    else:
        query = UserES().domain(domain).show_only_inactive()

    if user_type == MOBILE_USER_TYPE:
        query = query.mobile_users()
    if user_type == WEB_USER_TYPE:
        query = query.web_users()

    if role_id:
        query = query.role_id(role_id)
    if search_string:
        query = query.search_string_query(search_string, default_fields=['first_name', 'last_name', 'username'])

    location_ids = []
    if 'web_user_assigned_location_ids' in user_filters.keys():
        location_ids = SQLLocation.objects.get_locations_and_children_ids(
            user_filters['web_user_assigned_location_ids']
        )
    elif location_id:
        if selected_location_only:
            # This block will never execute for WEB_USER_TYPE
            location_ids = [location_id]
        else:
            location_ids = SQLLocation.objects.get_locations_and_children_ids([location_id])

    if location_ids:
        query = query.location(location_ids)

    return query


def count_mobile_users_by_filters(domain, user_filters):
    return _get_users_by_filters(domain, MOBILE_USER_TYPE, user_filters, count_only=True)


def count_web_users_by_filters(domain, user_filters):
    return _get_users_by_filters(domain, WEB_USER_TYPE, user_filters, count_only=True)


def get_mobile_users_by_filters(domain, user_filters):
    return _get_users_by_filters(domain, MOBILE_USER_TYPE, user_filters, count_only=False)


def get_web_users_by_filters(domain, user_filters):
    return _get_users_by_filters(domain, WEB_USER_TYPE, user_filters, count_only=False)


def _get_users_by_filters(domain, user_type, user_filters, count_only=False):
    """
    Returns users in domain per given filters. If user_filters is empty,
        returns all users in the domain

    args:
        user_type: MOBILE_USER_TYPE or WEB_USER_TYPE
        user_filters: a dict with below structure.
            {'role_id': <Role ID to filter users by>,
             'search_string': <string to search users by username>,
             'location_id': <Location ID to filter users by>,
             'selected_location_only: <Select only users at specific location, not descendants also>,
             'user_active_status': <User status (active/inactive) to filter by>,
             'web_user_assigned_location_ids': <Web User assigned locations>
             }
    kwargs:
        count_only: If True, returns count of search results
    """
    filters_applied = any([
        user_filters.get(f, None)
        for f in ['role_id', 'search_string', 'location_id', 'web_user_assigned_location_ids']
    ]) or type(user_filters.get('user_active_status', None)) == bool
    if not count_only and not filters_applied:
        if user_type == MOBILE_USER_TYPE:
            return get_all_commcare_users_by_domain(domain)
        if user_type == WEB_USER_TYPE:
            return get_all_web_users_by_domain(domain)
    else:
        query = _get_es_query(domain, user_type, user_filters)
        if count_only:
            return query.count()
        user_ids = query.scroll_ids()
        return map(CouchUser.wrap_correctly, iter_docs(CommCareUser.get_db(), user_ids))


def count_invitations_by_filters(domain, user_filters):
    return _get_invitations_by_filters(domain, user_filters, count_only=True)


def get_invitations_by_filters(domain, user_filters):
    return _get_invitations_by_filters(domain, user_filters)


def _get_invitations_by_filters(domain, user_filters, count_only=False):
    """
    Similar to _get_users_by_filters, but applites to invitations.

    Applies "search_string" filter to the invitations' emails. This does not
    support ES search syntax, it's just a case-insensitive substring search.
    Ignores any other filters.
    """
    filters = {}
    search_string = user_filters.get("search_string", None)
    if search_string:
        filters["email__icontains"] = search_string
    role_id = user_filters.get("role_id", None)
    if role_id:
        role = UserRole.objects.by_couch_id(role_id)
        filters["role"] = role.get_qualified_id()

    invitations = Invitation.by_domain(domain, **filters)
    if count_only:
        return invitations.count()
    return invitations


def get_all_user_ids_by_domain(domain, include_web_users=True, include_mobile_users=True):
    """Return generator of user IDs"""
    return (row['id'] for row in get_all_user_rows(
        domain,
        include_web_users=include_web_users,
        include_mobile_users=include_mobile_users
    ))


def get_all_usernames_by_domain(domain):
    """Returns generator of all usernames by domain regardless of their active status"""
    return (row['key'][3] for row in get_all_user_rows(domain, include_web_users=True))


def get_all_user_id_username_pairs_by_domain(domain, include_web_users=True, include_mobile_users=True):
    """Return pairs of user IDs and usernames by domain."""
    return ((row['id'], row['key'][3]) for row in get_all_user_rows(
        domain,
        include_web_users=include_web_users,
        include_mobile_users=include_mobile_users
    ))


def get_active_web_usernames_by_domain(domain):
    return (row['key'][3] for row in get_all_user_rows(domain, include_mobile_users=False, include_inactive=False))


def get_web_user_count(domain, include_inactive=True):
    return sum([
        row['value']
        for row in get_all_user_rows(
            domain,
            include_web_users=True,
            include_mobile_users=False,
            include_inactive=include_inactive,
            count_only=True
        ) if row
    ])


def get_mobile_user_count(domain, include_inactive=True):
    return sum([
        row['value']
        for row in get_all_user_rows(
            domain,
            include_web_users=False,
            include_mobile_users=True,
            include_inactive=include_inactive,
            count_only=True
        ) if row
    ])


def get_mobile_user_ids(domain, include_inactive=True):
    return {
        row['id']
        for row in get_all_user_rows(
            domain,
            include_web_users=False,
            include_mobile_users=True,
            include_inactive=include_inactive,
            count_only=False
        ) if row
    }


def get_all_user_rows(domain, include_web_users=True, include_mobile_users=True,
                      include_inactive=True, count_only=False, include_docs=False):
    from corehq.apps.users.models import CommCareUser, WebUser
    assert include_web_users or include_mobile_users

    doc_types = []
    if include_mobile_users:
        doc_types.append(CommCareUser.__name__)
    if include_web_users:
        doc_types.append(WebUser.__name__)

    states = ['active']
    if include_inactive:
        states.append('inactive')

    for flag in states:
        for doc_type in doc_types:
            key = [flag, domain, doc_type]
            for row in CommCareUser.get_db().view(
                    'users/by_domain',
                    startkey=key,
                    endkey=key + [{}],
                    reduce=count_only,
                    include_docs=include_docs
            ):
                yield row


def get_user_docs_by_username(usernames):
    return [
        ret['doc'] for ret in _get_user_results_by_username(usernames)
    ]


def get_existing_usernames(usernames):
    return {
        ret['key'] for ret in _get_user_results_by_username(usernames, include_docs=False)
    }.union(
        ret['key'] for ret in _get_deleted_user_results_by_username(usernames)
    )


def _get_user_results_by_username(usernames, include_docs=True):
    return CouchUser.get_db().view(
        'users/by_username',
        keys=list(usernames),
        reduce=False,
        include_docs=include_docs,
    ).all()


def _get_deleted_user_results_by_username(usernames):
    return CouchUser.get_db().view(
        'deleted_users_by_username/view',
        keys=list(usernames),
        reduce=False,
        include_docs=False,
    ).all()


def get_all_user_ids():
    return [res['id'] for res in CouchUser.get_db().view(
        'users/by_username',
        reduce=False,
    ).all()]


@unit_testing_only
def delete_all_users():
    from django.contrib.auth.models import User

    def _clear_cache(doc):
        user = CouchUser.wrap_correctly(doc, allow_deleted_doc_types=True)
        user.clear_quickcache_for_user()
    iter_bulk_delete(CommCareUser.get_db(), get_all_user_ids(), doc_callback=_clear_cache)
    User.objects.all().delete()


@unit_testing_only
def hard_delete_deleted_users():
    # Hard deleted the deleted users to truncate the view
    db_view = CommCareUser.get_db().view('deleted_users_by_username/view', reduce=False)
    deleted_user_ids = [row['id'] for row in db_view]
    iter_bulk_delete(CommCareUser.get_db(), deleted_user_ids)


def get_deleted_user_by_username(cls, username):
    result = cls.get_db().view('deleted_users_by_username/view',
                               key=username,
                               include_docs=True,
                               reduce=False
                               ).first()
    return cls.wrap_correctly(result['doc']) if result else None


def user_exists(username):
    """
    :param username:
    :return: namedtuple(exists:bool, is_deleted:bool)
    """
    result = CommCareUser.get_db().view(
        'users/by_username',
        key=username,
        include_docs=False,
        reduce=False,
    )
    if result:
        return UserExists(True, False)

    result = CommCareUser.get_db().view(
        'deleted_users_by_username/view',
        key=username,
        include_docs=False,
        reduce=False
    ).count()
    exists = bool(result)
    return UserExists(exists, exists)


@quickcache(['domain'])
def get_practice_mode_mobile_workers(domain):
    """
    Returns list of practice mode mobile workers formatted for HTML select
    """
    return (
        UserES()
        .domain(domain)
        .mobile_users()
        .is_practice_user()
        .fields(['_id', 'username'])
        .run().hits
    )


def get_all_user_search_query(search_string):
    query = (UserES()
             .remove_default_filters()
             .OR(web_users(), mobile_users()))
    if search_string:
        fields = ['username', 'first_name', 'last_name', 'phone_numbers',
                  'domain_membership.domain', 'domain_memberships.domain']
        query = query.search_string_query(search_string, fields)
    return query
