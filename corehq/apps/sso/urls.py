from django.conf.urls import include, url

from corehq.apps.sso.views.saml import (
    sso_saml_metadata,
    sso_saml_acs,
    sso_saml_login,
    sso_debug_user_data,
    sso_test_create_user,
)

saml_urls = [
    url(r'^metadata/$', sso_saml_metadata, name='sso_saml_metadata'),
    url(r'^acs/$', sso_saml_acs, name='sso_saml_acs'),
    url(r'^debug/$', sso_debug_user_data, name='sso_debug_user_data'),
    url(r'^login/$', sso_saml_login, name='sso_saml_login'),
    url(r'^create/$', sso_test_create_user, name='sso_test_create_user'),
]

urlpatterns = [
    url(r'^saml2/', include(saml_urls)),
]
