import requests

from corehq.apps.sso.exceptions import EntraVerificationFailed


class MSGraphIssue:
    HTTP_ERROR = "http_error"
    VERIFICATION_ERROR = "verification_error"
    EMPTY_ERROR = "empty_error"


def get_all_members_of_the_idp_from_entra(idp):
    import msal
    authority_base_url = "https://login.microsoftonline.com/"
    authority = f"{authority_base_url}{idp.api_host}"

    config = {
        "authority": authority,
        "client_id": idp.api_id,
        "scope": ["https://graph.microsoft.com/.default"],
        "secret": idp.api_secret,
        "endpoint": "https://graph.microsoft.com/v1.0/users"
    }

    # Create a preferably long-lived app instance which maintains a token cache.
    app = msal.ConfidentialClientApplication(
        config["client_id"], authority=config["authority"],
        client_credential=config["secret"],
    )
    # looks up a token from cache
    result = app.acquire_token_silent(config["scope"], account=None)
    # try:
    if not result:
        result = app.acquire_token_for_client(scopes=config["scope"])
    if "access_token" in result:
        # Calling graph using the access token
        response = requests.get(
            config["endpoint"],
            headers={'Authorization': 'Bearer ' + result['access_token']},
        )
        response.raise_for_status()  # Raises an error for bad status
        graph_data = response.json()

        user_principal_names = [user["userPrincipalName"] for user in graph_data["value"]]
        return user_principal_names
    else:
        raise EntraVerificationFailed(result.get('error', {}).get('code', 'Unknown'),
                                      result.get('error', {}).get('message', 'No error message provided.'))
