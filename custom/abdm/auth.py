from rest_framework.authentication import TokenAuthentication
from rest_framework.exceptions import AuthenticationFailed

from custom.abdm.models import ABDMUser


class ABDMUserAuthentication(TokenAuthentication):

    def authenticate_credentials(self, token):
        if not token:
            return None, None
        try:
            user = ABDMUser.objects.get(access_token=token)
        except ABDMUser.DoesNotExist:
            raise AuthenticationFailed('Unauthorized. Please re-sync.')
        if user.is_token_expired:
            raise AuthenticationFailed('Token expired. Please re-sync.')
        return user, None
