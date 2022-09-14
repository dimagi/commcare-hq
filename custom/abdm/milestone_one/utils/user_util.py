from django.contrib.auth import authenticate

from rest_framework.authtoken.models import Token


def get_abdm_api_token(username, password):
    print(f"Getting token for user {username}")
    user = authenticate(username=username, password=password)
    if not user:
        return None
    token, _ = Token.objects.get_or_create(user=user)
    print(f"Received token {len(token.key)}")
    return token.key
