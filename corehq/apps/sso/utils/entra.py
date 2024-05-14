import json
import requests

from corehq.apps.sso.exceptions import EntraVerificationFailed, EntraUnsupportedType


class MSGraphIssue:
    HTTP_ERROR = "http_error"
    VERIFICATION_ERROR = "verification_error"
    EMPTY_ERROR = "empty_error"
    UNSUPPORTED_ERROR = "unsupported_error"
    OTHER_ERROR = "other_error"


class MSOdataType:
    USER = "#microsoft.graph.user"
    GROUP = "#microsoft.graph.group"


ENDPOINT_BASE_URL = "https://graph.microsoft.com/v1.0"


def get_all_members_of_the_idp_from_entra(idp):
    import msal
    config = configure_idp(idp)

    # Create a preferably long-lived app instance which maintains a token cache.
    app = msal.ConfidentialClientApplication(
        config["client_id"], authority=config["authority"],
        client_credential=config["secret"],
    )

    token = get_access_token(app, config)

    # microsoft.graph.appRoleAssignment's property doesn't have userPrincipalName
    user_principal_ids = get_all_user_ids_in_app(token, config["client_id"])

    if len(user_principal_ids) == 0:
        return []

    user_principal_names = get_user_principal_names(user_principal_ids, token)

    return user_principal_names


def configure_idp(idp):
    authority_base_url = "https://login.microsoftonline.com/"
    authority = f"{authority_base_url}{idp.api_host}"

    return {
        "authority": authority,
        "client_id": idp.api_id,
        "scope": ["https://graph.microsoft.com/.default"],
        "secret": idp.api_secret,
    }


def get_user_principal_names(user_ids, token):
    # Prepare batch request
    batch_payload = {
        "requests": [
            {
                "id": str(i),
                "method": "GET",
                "url": f"/users/{principal_id}?$select=userPrincipalName"
            } for i, principal_id in enumerate(user_ids)
        ]
    }
    # Send batch request
    batch_response = requests.post(
        f'{ENDPOINT_BASE_URL}/$batch',
        headers={'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json'},
        data=json.dumps(batch_payload)
    )
    batch_response.raise_for_status()
    batch_result = batch_response.json()

    for resp in batch_result['responses']:
        if 'body' in resp and 'error' in resp['body']:
            raise EntraVerificationFailed(resp['body']['error']['code'], resp['body']['message'])

    # Extract userPrincipalName from batch response
    user_principal_names = [
        resp['body']['userPrincipalName'] for resp in batch_result['responses']
        if 'body' in resp and 'userPrincipalName' in resp['body']
    ]
    return user_principal_names


def get_access_token(app, config):
    # looks up a token from cache
    result = app.acquire_token_silent(config["scope"], account=None)
    if not result:
        result = app.acquire_token_for_client(scopes=config["scope"])
    if "access_token" not in result:
        raise EntraVerificationFailed(result.get('error', {}),
                                      result.get('error_description', 'No error description provided'))
    return result.get("access_token")


def get_all_user_ids_in_app(token, app_id):
    endpoint = (f"{ENDPOINT_BASE_URL}/servicePrincipals(appId='{app_id}')/"
               f"appRoleAssignedTo?$select=principalId, principalType")
    # Calling graph using the access token
    response = requests.get(
        endpoint,
        headers={'Authorization': 'Bearer ' + token},
    )
    response.raise_for_status()  # Raises an error for bad status
    assignments = response.json()

    user_ids = set()
    group_queue = []

    # Property principalType can either be User, Group or ServicePrincipal
    for assignment in assignments["value"]:
        if assignment["principalType"] == "User":
            user_ids.add(assignment["principalId"])
        elif assignment["principalType"] == "Group":
            group_queue.append(assignment["principalId"])
        else:
            raise EntraUnsupportedType("Nested applications (ServicePrincipal members) are not supported. "
                                       "Please include only Users or Groups as members of this SSO application")

    for group_id in group_queue:
        members_data = get_group_members(group_id, token)
        for member in members_data.get("value", []):
            # Only direct user in the group will have access to the application
            # Nested group won't have access to the application
            if member["@odata.type"] == MSOdataType.USER:
                user_ids.add(member["id"])

    return user_ids


def get_group_members(group_id, token):
    endpoint = f"{ENDPOINT_BASE_URL}/groups/{group_id}/members?$select=id"
    headers = {'Authorization': 'Bearer ' + token}
    response = requests.get(endpoint, headers=headers)
    response.raise_for_status()
    return response.json()
