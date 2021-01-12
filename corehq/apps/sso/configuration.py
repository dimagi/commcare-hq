import datetime

from onelogin.saml2.constants import OneLogin_Saml2_Constants
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
            "binding": OneLogin_Saml2_Constants.BINDING_HTTP_POST,
        },
        "singleLogoutService": {
            "url": "{}{}".format(
                get_url_base(),
                reverse("sso_saml_sls", args=(identity_provider.slug,))
            ),
            "binding": OneLogin_Saml2_Constants.BINDING_HTTP_REDIRECT,
        },
        "attributeConsumingService": {
            "serviceName": "CommCare HQ",
            "serviceDescription": "SSO for CommCare HQ",
            # "requestedAttributes": [
            #     {
            #         "name": "",
            #         "isRequired": false,
            #         "nameFormat": "",
            #         "friendlyName": "",
            #         "attributeValue": []
            #     }
            # ]
        },
        "NameIDFormat": OneLogin_Saml2_Constants.NAMEID_EMAIL_ADDRESS,
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
    metadata_valid_until = datetime.datetime.utcnow() + datetime.timedelta(days=3)
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
            "failOnAuthnContextMismatch": True,  # very important
            "signatureAlgorithm": "http://www.w3.org/2001/04/xmldsig-more#rsa-sha256",
            "digestAlgorithm": "http://www.w3.org/2001/04/xmlenc#sha256",
            "metadataValidUntil": metadata_valid_until.isoformat(),
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
