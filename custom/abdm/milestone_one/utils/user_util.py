import logging

from corehq.toggles import RESTORE_ADD_ABDM_TOKEN
from custom.abdm.models import ABDMUser
from casexml.apps.phone.xml import get_custom_user_data_for_restore

logger = logging.getLogger(__name__)


def get_abdm_api_token(username):
    user, _ = ABDMUser.objects.get_or_create(username=username)
    if not user.access_token:
        user.generate_token()
    return user.access_token


@get_custom_user_data_for_restore.extend()
def get_abdm_user_data(restore_user):
    if RESTORE_ADD_ABDM_TOKEN.enabled(restore_user.domain):
        return {"abdm_api_token": get_abdm_api_token(restore_user.username)}
