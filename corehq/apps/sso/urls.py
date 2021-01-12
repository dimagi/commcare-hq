from django.conf.urls import include, url

from corehq.apps.sso.views import (
    sso_saml_metadata,
    sso_saml_acs,
    sso_saml_login,
    sso_saml_sls,
    sso_saml_logout,
    index,
    attrs,
)

saml_urls = [
    url(r'^metadata/$', sso_saml_metadata, name='sso_saml_metadata'),
    url(r'^acs/$', sso_saml_acs, name='sso_saml_acs'),
    url(r'^sls/$', sso_saml_sls, name='sso_saml_sls'),
    url(r'^logout/$', sso_saml_logout, name='sso_saml_logout'),
    url(r'^login/$', sso_saml_login, name='sso_saml_login'),
    url(r'^test/$', index, name='sso_index'),
    url(r'^attrs/$', attrs, name='attrs'),
]

urlpatterns = [
    url(r'^saml2/', include(saml_urls)),
]
