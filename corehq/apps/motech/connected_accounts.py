import os
from uuid import uuid4
from authproxy_client import Credential, BasicAuth
from corehq.apps.motech.authproxy import authproxy_client
from corehq.apps.motech.models import ConnectedAccount


def save_openmrs_account(domain, url, username, password):
    try:
        account = ConnectedAccount.objects.get(
            domain=domain, server_type=ConnectedAccount.OPENMRS)
    except ConnectedAccount.DoesNotExist:
        account = ConnectedAccount(
            domain=domain,
            server_type=ConnectedAccount.OPENMRS,
            token=uuid4(),
            # os.urandom for cryptographically-random 128-bit key
            token_password=os.urandom(16),
        )

    account.server_url = url
    account.server_username = username
    account.save()

    credential = Credential(
        target=url,
        auth=BasicAuth(
            username=username,
            password=password,
        )
    )
    authproxy_client.create_or_update_credential(
        account.token, target=credential.target, auth=credential.auth)
    return authproxy_client.requests(account.token)


def get_openmrs_requests_object(domain):
    account = get_openmrs_account(domain)

    if account:
        return authproxy_client.requests(account.token)
    else:
        return None


def get_openmrs_account(domain):
    try:
        return ConnectedAccount.objects.get(
            domain=domain, server_type=ConnectedAccount.OPENMRS)
    except ConnectedAccount.DoesNotExist:
        return None
