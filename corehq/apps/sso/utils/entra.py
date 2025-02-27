import json
import requests

from django.utils.translation import gettext_lazy as _

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
MS_BATCH_LIMIT = 20


def get_all_usernames_of_the_idp_from_entra(idp):
    import msal
    config = _configure_idp(idp)

    # Create a preferably long-lived app instance which maintains a token cache.
    try:
        app = msal.ConfidentialClientApplication(
            config["client_id"], authority=config["authority"],
            client_credential=config["secret"],
        )
    except ValueError as e:
        if "check your tenant name" in str(e):
            raise EntraVerificationFailed(error="invalid_tenant",
                                          message=_("Please double check your tenant id is correct"))
        else:
            raise e

    token = _get_access_token(app, config)

    # microsoft.graph.appRoleAssignment's property doesn't have userPrincipalName
    user_principal_ids = _get_all_user_ids_in_app(token, config["client_id"])

    if len(user_principal_ids) == 0:
        return []

    user_principal_names = _get_user_principal_names(user_principal_ids, token)

    return user_principal_names


def _configure_idp(idp):
    authority_base_url = "https://login.microsoftonline.com/"
    authority = f"{authority_base_url}{idp.api_host}"

    return {
        "authority": authority,
        "client_id": idp.api_id,
        "scope": ["https://graph.microsoft.com/.default"],
        "secret": idp.api_secret,
    }


def _get_user_principal_names(user_ids, token):
    # Convert set to list to make it subscriptable
    user_ids = list(user_ids)
    #JSON batch requests are currently limited to 20 individual requests.
    user_id_chunks = [user_ids[i:i + MS_BATCH_LIMIT] for i in range(0, len(user_ids), MS_BATCH_LIMIT)]

    user_principal_names = []

    for chunk in user_id_chunks:
        batch_payload = {
            "requests": [
                {
                    "id": str(i),
                    "method": "GET",
                    "url": f"/users/{principal_id}?$select=userPrincipalName,accountEnabled"
                } for i, principal_id in enumerate(chunk)
            ]
        }

        # Send batch request
        batch_response = requests.post(
            f'{ENDPOINT_BASE_URL}/$batch',
            headers={'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json'},
            data=json.dumps(batch_payload)
        )

        try:
            batch_response.raise_for_status()
        except requests.exceptions.HTTPError as e:
            # Append the response body to the HTTPError message
            error_message = f"{e.response.status_code} {e.response.reason} - {batch_response.text}"
            raise requests.exceptions.HTTPError(error_message, response=e.response)

        batch_result = batch_response.json()
        for resp in batch_result['responses']:
            if 'body' in resp and 'error' in resp['body']:
                raise EntraVerificationFailed(resp['body']['error']['code'], resp['body']['message'])

        # Extract userPrincipalName from batch response
        for resp in batch_result['responses']:
            if ('body' in resp and 'userPrincipalName' in resp['body']
            and resp['body'].get('accountEnabled') is True):
                user_principal_names.append(resp['body']['userPrincipalName'])

    return user_principal_names


def _get_access_token(app, config):
    # looks up a token from cache
    result = app.acquire_token_silent(config["scope"], account=None)
    if not result:
        result = app.acquire_token_for_client(scopes=config["scope"])
    if "access_token" not in result:
        raise EntraVerificationFailed(result.get('error', {}),
                                      result.get('error_description', _('No error description provided')))
    return result.get("access_token")


def _get_all_user_ids_in_app(token, app_id):
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
            raise EntraUnsupportedType(_("Nested applications (ServicePrincipal members) are not supported. "
                                       "Please include only Users or Groups as members of this SSO application"))

    for group_id in group_queue:
        members_data = _get_group_members(group_id, token)
        for member in members_data:
            # Only direct user in the group will have access to the application
            # Nested group won't have access to the application
            if member["@odata.type"] == MSOdataType.USER:
                user_ids.add(member["id"])

    return user_ids


def _get_group_members(group_id, token):
    members = []
    endpoint = f"{ENDPOINT_BASE_URL}/groups/{group_id}/members?$select=id"
    headers = {'Authorization': 'Bearer ' + token}

    while endpoint:
        response = requests.get(endpoint, headers=headers)
        response.raise_for_status()
        data = response.json()
        members.extend(data.get('value', []))

        # Check for a nextLink to continue paging through results
        endpoint = data.get('@odata.nextLink')

    return members
