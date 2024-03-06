from django.urls import include, re_path as url

from corehq.apps.sso.views.oidc import (
    sso_oidc_login,
    sso_oidc_auth,
    sso_oidc_logout,
)
from corehq.apps.sso.views.saml import (
    sso_saml_metadata,
    sso_saml_acs,
    sso_saml_login,
)

saml_urls = [
    url(r'^metadata/$', sso_saml_metadata, name='sso_saml_metadata'),
    url(r'^acs/$', sso_saml_acs, name='sso_saml_acs'),
    url(r'^login/$', sso_saml_login, name='sso_saml_login'),
]

oidc_urls = [
    url(r'^login/$', sso_oidc_login, name='sso_oidc_login'),
    url(r'^auth/$', sso_oidc_auth, name='sso_oidc_auth'),
    url(r'^logout/$', sso_oidc_logout, name='sso_oidc_logout'),
]

urlpatterns = [
    url(r'^saml2/', include(saml_urls)),
    url(r'^oidc/', include(oidc_urls)),
]
