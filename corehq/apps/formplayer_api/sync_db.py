from corehq.apps.formplayer_api.smsforms.api import _get_response
from corehq.apps.users.models import CouchUser
from corehq.toggles import FORMPLAYER_USE_LIVEQUERY


def sync_db(domain, username, restore_as):
    user = CouchUser.get_by_username(username)
    assert user.is_member_of(domain)
    user_id = user.user_id
    use_livequery = FORMPLAYER_USE_LIVEQUERY.enabled(domain)
    data = {
        'action': 'change_locale',
        'username': username,
        'domain': domain,
        'restoreAs': restore_as,
        'useLiveQuery': use_livequery,
    }
    return _get_response(data, user_id=user_id)
