from django.core.files.uploadedfile import SimpleUploadedFile
from django_prbac.models import Role

from django.contrib.sessions.middleware import SessionMiddleware

from corehq.apps.accounting.models import (
    SoftwarePlan,
    SoftwarePlanEdition,
    SoftwarePlanVisibility,
    SoftwareProductRate,
    SoftwarePlanVersion,
)
from corehq.apps.sso import certificates
from corehq.apps.accounting.tests import generator as accounting_gen

from corehq.util.test_utils import unit_testing_only
from corehq.apps.sso.models import (
    IdentityProvider,
)


@unit_testing_only
def create_idp(slug, account, include_certs=False):
    idp = IdentityProvider(
        name=f"Azure AD for {account.name}",
        slug=slug,
        owner=account,
    )
    idp.save()
    if include_certs:
        idp.create_service_provider_certificate()
        idp.entity_id = "https://testidp.com/saml2/entity_id"
        idp.login_url = "https://testidp.com/saml2/login"
        idp.logout_url = "https://testidp.com/saml2/logout"
        key_pair = certificates.create_key_pair()
        cert = certificates.create_self_signed_cert(key_pair)
        idp.idp_cert_public = certificates.get_public_key(cert)
        idp.date_idp_cert_expiration = certificates.get_expiration_date(cert)
        idp.save()
    return idp


@unit_testing_only
def get_billing_account_for_idp():
    billing_contact = accounting_gen.create_arbitrary_web_user_name()
    dimagi_user = accounting_gen.create_arbitrary_web_user_name(is_dimagi=True)
    return accounting_gen.billing_account(
        dimagi_user, billing_contact, is_customer_account=True
    )


@unit_testing_only
def get_enterprise_plan():
    enterprise_plan = SoftwarePlan.objects.create(
        name="Helping Earth INGO Enterprise Plan",
        description="Enterprise plan for Helping Earth",
        edition=SoftwarePlanEdition.ENTERPRISE,
        visibility=SoftwarePlanVisibility.INTERNAL,
        is_customer_software_plan=True,
    )
    first_product_rate = SoftwareProductRate.objects.create(
        monthly_fee=3000,
        name="HQ Enterprise"
    )
    return SoftwarePlanVersion.objects.create(
        plan=enterprise_plan,
        role=Role.objects.first(),
        product_rate=first_product_rate
    )


@unit_testing_only
def create_request_session(request, use_saml_sso=False, use_oidc_sso=False):
    def get_response(request):
        raise AssertionError("should not get here")
    SessionMiddleware(get_response).process_request(request)
    request.session.save()
    if use_saml_sso:
        request.session['samlSessionIndex'] = '_7c84c96e-8774-4e64-893c-06f91d285100'
    if use_oidc_sso:
        request.session["oidc_state"] = '_7c84c96e-8774-4e64-893c-06f91d285100'


@unit_testing_only
def store_full_name_in_saml_user_data(request, first_name, last_name):
    request.session['samlUserdata'] = {
        'http://schemas.xmlsoap.org/ws/2005/05/identity/claims/givenname': [first_name],
        'http://schemas.xmlsoap.org/ws/2005/05/identity/claims/surname': [last_name],
    }


@unit_testing_only
def store_display_name_in_saml_user_data(request, display_name):
    request.session['samlUserdata'] = {
        'http://schemas.microsoft.com/identity/claims/displayname': [display_name],
    }


@unit_testing_only
def store_full_name_in_oidc_user_data(request, first_name, last_name):
    request.session['oidcUserData'] = {
        'given_name': first_name,
        'family_name': last_name,
    }


@unit_testing_only
def store_display_name_in_oidc_user_data(request, display_name):
    request.session['oidcUserData'] = {
        'name': display_name,
    }


@unit_testing_only
def get_public_cert_file(expiration_in_seconds=certificates.DEFAULT_EXPIRATION):
    key_pair = certificates.create_key_pair()
    cert = certificates.create_self_signed_cert(
        key_pair,
        expiration_in_seconds
    )
    return SimpleUploadedFile(
        "certificate.cer",
        cert.public_bytes(certificates.serialization.Encoding.PEM),
        content_type="application/x-x509-ca-cert",
    )


@unit_testing_only
def get_bad_cert_file(bad_cert_data):
    return SimpleUploadedFile(
        "certificate.cer",
        bad_cert_data,
        content_type="application/x-x509-ca-cert",
    )
