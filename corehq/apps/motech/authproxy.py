from authproxy_client import AuthProxyClient
from django.conf import settings


def _authproxy_client_get_password(token):
    from .models import ConnectedAccount
    try:
        return ConnectedAccount.objects.values_list('token_password', flat=True).get(token=token)
    except ConnectedAccount.DoesNotExist:
        raise KeyError(token)

if settings.AUTHPROXY_URL:
    authproxy_client = AuthProxyClient(
        settings.AUTHPROXY_URL,
        get_password=_authproxy_client_get_password,
        cert_file=settings.AUTHPROXY_CERT,
    )
else:
    authproxy_client = None
