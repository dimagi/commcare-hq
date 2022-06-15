from django.contrib import auth
from django.contrib.auth import logout
from django.http import HttpResponseRedirect, JsonResponse, HttpResponse
from django.shortcuts import redirect
from rest_framework.status import HTTP_401_UNAUTHORIZED

from corehq.apps.api.odata.views import add_odata_headers
from corehq.apps.sso.models import IdentityProviderProtocol
from corehq.util.view_utils import reverse, absolute_reverse
from corehq.apps.sso.decorators import identity_provider_required
from corehq.apps.sso.exceptions import SsoLoginFailed, OidcSsoError
from corehq.apps.sso.utils.login_helpers import process_async_signup_requests
from corehq.apps.sso.utils.message_helpers import show_sso_login_success_or_error_messages
from corehq.apps.sso.utils.oidc import (
    get_client_for_identity_provider,
    initialize_oidc_session,
    get_openid_provider_login_url,
    get_user_information_or_throw_error,
)
from corehq.apps.sso.utils.url_helpers import add_username_hint_to_login_url
from corehq.apps.sso.utils.view_helpers import render_sso_error, render_sso_user_login_failed


@identity_provider_required
def sso_oidc_login(request, idp_slug):
    client = get_client_for_identity_provider(request.idp)
    initialize_oidc_session(request)
    login_url = add_username_hint_to_login_url(
        get_openid_provider_login_url(client, request),
        request
    )
    return HttpResponseRedirect(login_url)


@identity_provider_required
def sso_oidc_auth(request, idp_slug):
    client = get_client_for_identity_provider(request.idp)
    try:
        user_info = get_user_information_or_throw_error(client, request)
        request.session['oidcUserData'] = user_info
        username = user_info['email'] if 'email' in user_info else user_info['preferred_username']
        user = auth.authenticate(
            request=request,
            username=username,
            idp_slug=idp_slug,
            is_handshake_successful=True,
        )
        show_sso_login_success_or_error_messages(request)

        if user:
            auth.login(request, user)
            process_async_signup_requests(request, user)

            if request.session["oidc_return_to"]:
                redirect_url = request.session["oidc_return_to"]
                del request.session["oidc_return_to"]
                return HttpResponseRedirect(redirect_url)

            return redirect("homepage")

    except OidcSsoError as error:
        return render_sso_error(request, error)
    except SsoLoginFailed:
        return render_sso_user_login_failed(request)
    return JsonResponse({
        "issue": True,
    })


@identity_provider_required
def sso_oidc_logout(request, idp_slug):
    # Only the OP would ever redirect to this view. We don't handle logging out from the OP.
    logout(request)
    return HttpResponseRedirect(reverse('login'))


@identity_provider_required
def sso_oidc_api_auth(request, idp_slug):
    return JsonResponse({
        "success": True,
        "bearer authorization uri": request.idp.login_url.replace('saml2', 'oauth2/authorize'),
    })


@identity_provider_required
def sso_oidc_fake_odata_feed(request, idp_slug):
    metadata_url = absolute_reverse("sso_oidc_fake_odata_metadata_view", args=(idp_slug,))
    data = {"@odata.context": f"{metadata_url}#feed", "value": [{"completed_time": "2021-03-02T10:03:56.844000Z", "form play_count": "1", "form_link": "https://staging.commcarehq.org/a/ccqa/reports/form_data/305fe039-bf5e-4edb-8f86-91e17e753ade/", "formid": "305fe039-bf5e-4edb-8f86-91e17e753ade", "hq_user": "ktripathy@dimagi.com", "number": "305fe039-bf5e-4edb-8f86-91e17e753ade", "received_on": "2021-03-02T10:03:57.233003Z", "started_time": "2021-03-02T10:03:54.469000Z", "username": "007"}, {"completed_time": "2021-03-24T10:54:38.493000Z", "form play_count": "1", "form_link": "https://staging.commcarehq.org/a/ccqa/reports/form_data/5949a002-fa6c-48bf-b0c3-6f6be66eed06/", "formid": "5949a002-fa6c-48bf-b0c3-6f6be66eed06", "hq_user": "sameena.shaik@fissionlabs.com", "number": "5949a002-fa6c-48bf-b0c3-6f6be66eed06", "received_on": "2021-03-24T10:54:38.695121Z", "started_time": "2021-03-24T10:54:35.143000Z", "username": "123"}, {"completed_time": "2021-03-24T12:17:34.978000Z", "form play_count": "1", "form_link": "https://staging.commcarehq.org/a/ccqa/reports/form_data/6f8f2eea-57f9-4a62-9102-007648955e9a/", "formid": "6f8f2eea-57f9-4a62-9102-007648955e9a", "hq_user": "sameena.shaik@fissionlabs.com", "number": "6f8f2eea-57f9-4a62-9102-007648955e9a", "received_on": "2021-03-24T12:17:35.222237Z", "started_time": "2021-03-24T12:17:33.487000Z", "username": "user241"}, {"completed_time": "2021-03-24T12:34:59.186000Z", "form play_count": "1", "form_link": "https://staging.commcarehq.org/a/ccqa/reports/form_data/28f1e529-5dd4-422a-9f69-8e4fcc9fa9f0/", "formid": "28f1e529-5dd4-422a-9f69-8e4fcc9fa9f0", "hq_user": "sameena.shaik@fissionlabs.com", "number": "28f1e529-5dd4-422a-9f69-8e4fcc9fa9f0", "received_on": "2021-03-24T12:34:59.483072Z", "started_time": "2021-03-24T12:34:57.003000Z", "username": "user241"}, {"completed_time": "2021-03-30T03:52:49.799000Z", "form play_count": "1", "form_link": "https://staging.commcarehq.org/a/ccqa/reports/form_data/1d575ed9-a3a6-4297-9f7f-02ff6d6ee5b3/", "formid": "1d575ed9-a3a6-4297-9f7f-02ff6d6ee5b3", "hq_user": "ktripathy@dimagi.com", "number": "1d575ed9-a3a6-4297-9f7f-02ff6d6ee5b3", "received_on": "2021-03-30T03:52:50.306155Z", "started_time": "2021-03-30T03:52:47.679000Z", "username": "007"}, {"completed_time": "2021-03-30T09:49:36.152000Z", "form play_count": "1", "form_link": "https://staging.commcarehq.org/a/ccqa/reports/form_data/734c6cc2-3ca6-4240-8a7a-f65897db0dcc/", "formid": "734c6cc2-3ca6-4240-8a7a-f65897db0dcc", "hq_user": "yamika.kodali@fissionlabs.com", "number": "734c6cc2-3ca6-4240-8a7a-f65897db0dcc", "received_on": "2021-03-30T09:49:36.328225Z", "started_time": "2021-03-30T09:49:33.692000Z", "username": "sample_user2"}, {"completed_time": "2021-04-21T10:33:56.838000Z", "form play_count": "1", "form_link": "https://staging.commcarehq.org/a/ccqa/reports/form_data/62e5d743-e5e7-4c5a-a4d4-7a00ab567743/", "formid": "62e5d743-e5e7-4c5a-a4d4-7a00ab567743", "hq_user": "sample_user1", "number": "62e5d743-e5e7-4c5a-a4d4-7a00ab567743", "received_on": "2021-04-21T10:33:58.240913Z", "started_time": "2021-04-21T10:33:54.981000Z", "username": "sample_user1"}, {"completed_time": "2021-04-30T06:15:39.594000Z", "form play_count": "1", "form_link": "https://staging.commcarehq.org/a/ccqa/reports/form_data/076b2acd-9864-476a-9031-68855311996e/", "formid": "076b2acd-9864-476a-9031-68855311996e", "hq_user": "ktripathy@dimagi.com", "number": "076b2acd-9864-476a-9031-68855311996e", "received_on": "2021-04-30T06:15:40.044902Z", "started_time": "2021-04-30T06:15:37.664000Z", "username": "007"}, {"completed_time": "2022-03-24T09:38:03.942000Z", "form play_count": "1", "form_link": "https://staging.commcarehq.org/a/ccqa/reports/form_data/7949808d-e853-4659-885f-f95119d6b6d0/", "formid": "7949808d-e853-4659-885f-f95119d6b6d0", "hq_user": "sameena.shaik@fissionlabs.com", "number": "7949808d-e853-4659-885f-f95119d6b6d0", "received_on": "2022-03-24T09:38:04.272357Z", "started_time": "2022-03-24T09:38:00.026000Z", "username": "123"}]}
    response = add_odata_headers(JsonResponse(data))
    if request.idp.protocol == IdentityProviderProtocol.SAML:
        authenticate_url = request.idp.entity_id.replace('saml2', 'oauth2/authorize')
        response["www-authenticate"] = f"Bearer authorization_uri={authenticate_url}"
    return response


@identity_provider_required
def sso_oidc_fake_odata_metadata_view(request, idp_slug):
    metadata = """<edmx:Edmx xmlns:edmx="http://docs.oasis-open.org/odata/ns/edmx" Version="4.0">
<edmx:DataServices>
<Schema xmlns="http://docs.oasis-open.org/odata/ns/edm" Namespace="CommCare">
<EntityType Name="feed">
<Key>
<PropertyRef Name="formid"/>
</Key>
<Property Name="number" Type="Edm.String"/>
<Property Name="formid" Type="Edm.String"/>
<Property Name="form play_count" Type="Edm.String"/>
<Property Name="completed_time" Type="Edm.DateTimeOffset"/>
<Property Name="started_time" Type="Edm.DateTimeOffset"/>
<Property Name="username" Type="Edm.String"/>
<Property Name="received_on" Type="Edm.DateTimeOffset"/>
<Property Name="form_link" Type="Edm.String"/>
<Property Name="hq_user" Type="Edm.String"/>
</EntityType>
<EntityContainer Name="Container">
<EntitySet Name="feed" EntityType="CommCare.feed"/>
</EntityContainer>
</Schema>
</edmx:DataServices>
</edmx:Edmx>"""
    return add_odata_headers(HttpResponse(metadata, content_type='application/xml'))


@identity_provider_required
def sso_oidc_fake_odata_service_view(request, idp_slug):
    service_document_content = {
        '@odata.context': absolute_reverse("sso_oidc_fake_odata_metadata_view", args=(idp_slug,)),
        'value': [{
            'name': 'feed',
            'kind': 'EntitySet',
            'url': 'feed',
        }]
    }
    return add_odata_headers(JsonResponse(service_document_content))
