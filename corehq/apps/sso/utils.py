from django.urls import reverse
import settings
from dimagi.utils.web import get_url_base


def get_saml2_config(identity_provider):
    sp_settings = {
        "entityId": "{}{}".format(
            get_url_base(),
            reverse("sso_saml_metadata", args=(identity_provider.slug,))
        ),
        "assertionConsumerService": {
            "url": "{}{}".format(
                get_url_base(),
                reverse("sso_saml_acs", args=(identity_provider.slug,))
            ),
            "binding": "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST"
        },
        "singleLogoutService": {
            "url": "{}{}".format(
                get_url_base(),
                reverse("sso_saml_sls", args=(identity_provider.slug,))
            ),
            "binding": "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-Redirect"
        },
        "NameIDFormat": "urn:oasis:names:tc:SAML:1.1:nameid-format:emailAddress",
        "x509cert": identity_provider.sp_cert_public,
        "privateKey": identity_provider.sp_cert_private,
    }

    if identity_provider.sp_rollover_cert_public:
        sp_settings['x509certNew'] = identity_provider.sp_rollover_cert_public

    saml_config = {
        "strict": True,
        "debug": settings.SAML2_DEBUG,
        "sp": sp_settings,
        "idp": {
            "entityId": identity_provider.entity_id,
            "singleSignOnService": {
                "url": identity_provider.login_url,
                "binding": "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-Redirect"
            },
            "singleLogoutService": {
                "url": identity_provider.logout_url,
                "binding": "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-Redirect"
            },
            "x509cert": identity_provider.idp_cert_public,
        },
    }

    saml_config.update(_get_advanced_saml2_settings())
    return saml_config


def _get_advanced_saml2_settings():
    return {
        "security": {
            "nameIdEncrypted": True,
            "authnRequestsSigned": True,
            "logoutRequestSigned": True,
            "logoutResponseSigned": True,
            "signMetadata": False,
            "wantMessagesSigned": True,
            "wantAssertionsSigned": True,
            "wantNameId": True,
            "wantNameIdEncrypted": True,
            "wantAssertionsEncrypted": True,
            "signatureAlgorithm": "http://www.w3.org/2001/04/xmldsig-more#rsa-sha256",
            "digestAlgorithm": "http://www.w3.org/2001/04/xmlenc#sha256",
        },
        "contactPerson": {
            "technical": {
                "givenName": "Accounts Team",
                "emailAddress": settings.ACCOUNTS_EMAIL,
            },
            "support": {
                "givenName": "Support Team",
                "emailAddress": settings.SUPPORT_EMAIL,
            },
        },
        "organization": {
            "en-US": {
                "name": "commcare_hq",
                "displayname": "CommCare HQ",
                "url": get_url_base(),
            },
        },
    }
