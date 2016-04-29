from itertools import imap
from django.conf import settings
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
