from itertools import imap
from django.conf import settings
from corehq.apps.users.models import CommCareUser
from dimagi.utils.couch.database import iter_docs, iter_bulk_delete


def get_all_commcare_users_by_domain(domain):
    """Returns all CommCareUsers by domain regardless of their active status"""
    from corehq.apps.users.models import CommCareUser

    def get_ids():
        for flag in ['active', 'inactive']:
            key = [flag, domain, CommCareUser.__name__]
            for user in CommCareUser.get_db().view(
                'users/by_domain',
                startkey=key,
                endkey=key + [{}],
                reduce=False,
                include_docs=False
            ):
                yield user['id']

    return imap(CommCareUser.wrap, iter_docs(CommCareUser.get_db(), _get_ids_by_domain(domain)))


def get_user_docs_by_username(usernames):
    from corehq.apps.users.models import CouchUser
    return [res['doc'] for res in CouchUser.get_db().view(
        'users/by_username',
        keys=list(usernames),
        reduce=False,
        include_docs=True,
    ).all()]


def get_all_user_ids():
    from corehq.apps.users.models import CouchUser
    return [res['id'] for res in CouchUser.get_db().view(
        'users/by_username',
        reduce=False,
    ).all()]


def delete_all_users():
    if not settings.UNIT_TESTING:
        raise Exception("You're not allowed to delete all users except in tests!")

    iter_bulk_delete(CommCareUser.get_db(), get_all_user_ids())
