from django.conf.urls import include, url

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

urlpatterns = [
    url(r'^saml2/', include(saml_urls)),
]
