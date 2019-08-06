from __future__ import absolute_import

from __future__ import unicode_literals
from collections import namedtuple

from corehq.apps.users.models import CommCareUser
from corehq.apps.es import UserES
from corehq.util.quickcache import quickcache
from corehq.util.test_utils import unit_testing_only
from dimagi.utils.couch.database import iter_docs, iter_bulk_delete
from six.moves import map


UserExists = namedtuple('UserExists', 'exists is_deleted')


def get_all_commcare_users_by_domain(domain):
    """Returns all CommCareUsers by domain regardless of their active status"""
    ids = get_all_user_ids_by_domain(domain, include_web_users=False)
    return map(CommCareUser.wrap, iter_docs(CommCareUser.get_db(), ids))


def get_commcare_users_by_filters(domain, user_filters, count_only=False):
    """
    Returns CommCareUsers in domain per given filters. If user_filters is empty
        returns all users in the domain

    args:
        user_filters: a dict with below structure.
            {'role_id': <Role ID to filter users by>,
             'search_string': <string to search users by username>,
             'location_id': <Location ID to filter users by>}
    kwargs:
        count_only: If True, returns count of search results
    """
    role_id = user_filters.get('role_id', None)
    search_string = user_filters.get('search_string', None)
    location_id = user_filters.get('location_id', None)
    if not any([role_id, search_string, location_id, count_only]):
        return get_all_commcare_users_by_domain(domain)

    query = UserES().domain(domain).mobile_users()

    if role_id:
        query = query.role_id(role_id)
    if search_string:
        query = query.search_string_query(search_string, default_fields=['first_name', 'last_name', 'username'])
    if location_id:
        query = query.location(location_id)

    if count_only:
        return query.count()
    user_ids = query.scroll_ids()
    return map(CommCareUser.wrap, iter_docs(CommCareUser.get_db(), user_ids))


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
    return [
        ret['key'] for ret in _get_user_results_by_username(usernames, include_docs=False)
    ]


def _get_user_results_by_username(usernames, include_docs=True):
    from corehq.apps.users.models import CouchUser
    return CouchUser.get_db().view(
        'users/by_username',
        keys=list(usernames),
        reduce=False,
        include_docs=include_docs,
    ).all()


def get_all_user_ids():
    from corehq.apps.users.models import CouchUser
    return [res['id'] for res in CouchUser.get_db().view(
        'users/by_username',
        reduce=False,
    ).all()]


@unit_testing_only
def delete_all_users():
    from corehq.apps.users.models import CouchUser
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
