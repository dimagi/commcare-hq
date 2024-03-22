from casexml.apps.phone.xml import get_custom_user_data_for_restore

from corehq.toggles import ABDM_INTEGRATION
from custom.abdm.models import ABDMUser


def _get_abdm_api_token(username, domain):
    user, _ = ABDMUser.objects.get_or_create(username=username, domain=domain)
    user.refresh_token()
    return user.access_token


@get_custom_user_data_for_restore.extend()
def get_abdm_user_data(restore_user):
    if ABDM_INTEGRATION.enabled(restore_user.domain):
        return {"abdm_api_token": _get_abdm_api_token(restore_user.username, restore_user.domain)}
    return {}
