import json
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
        "endpoint": f"https://graph.microsoft.com/v1.0/servicePrincipals(appId='{idp.api_id}')/"
                    "appRoleAssignedTo?$select=principalId, principalType"
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
        assignments = response.json()

        # microsoft.graph.appRoleAssignment's property doesn't  userPrincipalName
        # Property principalType can either be User, Group or ServicePrincipal
        principal_ids = {assignment["principalId"] for assignment in assignments["value"]
                         if assignment["principalType"] == "User"}

        # Prepare batch request
        batch_payload = {
            "requests": [
                {
                    "id": str(i),
                    "method": "GET",
                    "url": f"/users/{principal_id}?$select=userPrincipalName"
                } for i, principal_id in enumerate(principal_ids)
            ]
        }

        # Send batch request
        batch_response = requests.post(
            'https://graph.microsoft.com/v1.0/$batch',
            headers={'Authorization': 'Bearer ' + result['access_token'], 'Content-Type': 'application/json'},
            data=json.dumps(batch_payload)
        )
        batch_response.raise_for_status()
        batch_result = batch_response.json()

        # Extract userPrincipalName from batch response
        user_principal_names = [
            resp['body']['userPrincipalName'] for resp in batch_result['responses']
            if 'body' in resp and 'userPrincipalName' in resp['body']
        ]
        return user_principal_names
    else:
        raise EntraVerificationFailed(result.get('error', {}).get('code', 'Unknown'),
                                      result.get('error', {}).get('message', 'No error message provided.'))
