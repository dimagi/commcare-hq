from corehq.apps.formplayer_api.exceptions import FormplayerResponseException
from corehq.apps.formplayer_api.smsforms.api import _post_data
from corehq.apps.formplayer_api.utils import check_user_access


def sync_db(domain, username, restore_as=None):
    """Call Formplayer API to force a sync for a user."""
    user = check_user_access(domain, username, allow_enterprise=True)
    if restore_as:
        check_user_access(domain, restore_as)

    data = {
        'action': 'sync-db',
        'username': username,
        'domain': domain,
        'restoreAs': restore_as,
    }
    response_json = _post_data(data, user.user_id)
    if not response_json.get("status") == "accepted":
        raise FormplayerResponseException(response_json)
