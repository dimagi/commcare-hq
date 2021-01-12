from corehq.apps.formplayer_api.smsforms.api import _post_data
from corehq.apps.users.models import CouchUser
from corehq.toggles import FORMPLAYER_USE_LIVEQUERY


def sync_db(domain, username, restore_as=None):
    user = CouchUser.get_by_username(username)
    assert user.is_member_of(domain)
    user_id = user.user_id
    use_livequery = FORMPLAYER_USE_LIVEQUERY.enabled(domain)
    data = {
        'action': 'sync-db',
        'username': username,
        'domain': domain,
        'restoreAs': restore_as or username,
        'useLiveQuery': use_livequery,
    }
    response_json = _post_data(data, user_id)
    if not response_json.get("status") == "accepted":
        raise Exception(response_json)
