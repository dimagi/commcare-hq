from corehq.apps.users.models import CommCareUser
from corehq.util.couch import stale_ok


def update_analytics_indexes():
    """
    Mostly for testing; wait until analytics data sources are up to date
    so that calls to analytics functions return up-to-date

    (modeled very closely after the same function in couchforms.analytics)
    """
    CommCareUser.get_db().view('users/by_domain', limit=1).all()


def get_count_of_active_commcare_users_in_domain(domain):
    result = CommCareUser.get_db().view(
        'users/by_domain',
        startkey=['active', domain],
        endkey=['active', domain, {}],
        group=True,
        group_level=2,
        stale=stale_ok(),
    ).one()
    return result['value'] if result else 0
