import logging
from django.contrib.auth import authenticate
from django.contrib.auth.models import User

from rest_framework.authtoken.models import Token

logger = logging.getLogger(__name__)


def get_abdm_api_token(username, password, restore=False):
    logger.info(f"Getting token for user {username}")
    if restore:
        user = User.objects.filter(username=username).first()
    else:
        user = authenticate(username=username, password=password)
    if not user:
        return None
    token, _ = Token.objects.get_or_create(user=user)
    logger.info(f"Received token {len(token.key)}")
    return token.key
