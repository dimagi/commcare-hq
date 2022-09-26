import logging

from custom.abdm.models import ABDMUser

logger = logging.getLogger(__name__)


def get_abdm_api_token(username):
    user, _ = ABDMUser.objects.get_or_create(username=username)
    if not user.access_token:
        user.generate_token()
    return user.access_token
