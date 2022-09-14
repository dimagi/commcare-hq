from rest_framework.authentication import TokenAuthentication
from rest_framework.exceptions import AuthenticationFailed
from custom.abdm.models import ABDMUser


class UserAuthentication(TokenAuthentication):

    def authenticate(self, request):
        print("\n".join(request.META.keys()))
        access_token = request.META.get('HTTP_AUTHORIZATION', "")
        print(access_token)
        token = access_token.split()[-1]
        if not token:
            return None
        try:
            user: ABDMUser = ABDMUser.objects.get(access_token=token)
        except ABDMUser.DoesNotExist:
            raise AuthenticationFailed('Unauthorized')
        if not user.is_token_valid:
            raise AuthenticationFailed('Invalid Token')
        return (user, None)
