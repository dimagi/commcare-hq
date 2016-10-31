from itertools import imap
from corehq.apps.users.models import CommCareUser
from corehq.util.test_utils import unit_testing_only
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

    return imap(CommCareUser.wrap, iter_docs(CommCareUser.get_db(), get_ids()))


def get_all_usernames_by_domain(domain):
    """Returns all usernames by domain regardless of their active status"""
    from corehq.apps.users.models import CommCareUser, WebUser

    def get_usernames():
        for flag in ['active', 'inactive']:
            for doc_type in [CommCareUser.__name__, WebUser.__name__]:
                key = [flag, domain, doc_type]
                for row in CommCareUser.get_db().view(
                        'users/by_domain',
                        startkey=key,
                        endkey=key + [{}],
                        reduce=False,
                        include_docs=False
                ):
                    yield row['key'][3]

    return list(get_usernames())


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
