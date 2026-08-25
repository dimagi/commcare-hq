from tastypie.authorization import ReadOnlyAuthorization

from corehq.apps.api.openapi.security import (
    SECURITY_REQUIREMENT,
    SECURITY_SCHEMES,
    required_permission,
)
from corehq.apps.api.resources.auth import (
    LoginAndDomainAuthentication,
    RequirePermissionAuthentication,
)
from corehq.apps.api.resources.meta import CustomResourceMeta
from corehq.apps.users.models import HqPermissions


class FakeMeta:
    def __init__(self, authentication):
        self.authentication = authentication


class FakeResource:
    def __init__(self, authentication):
        self._meta = FakeMeta(authentication)


def test_api_key_scheme_documents_the_header_format():
    api_key = SECURITY_SCHEMES['ApiKeyAuth']
    assert api_key['type'] == 'apiKey'
    assert api_key['in'] == 'header'
    assert api_key['name'] == 'Authorization'
    assert 'ApiKey <username>:<api_key>' in api_key['description']


def test_all_supported_schemes_are_declared():
    assert set(SECURITY_SCHEMES) == {
        'ApiKeyAuth',
        'BasicAuth',
        'DigestAuth',
        'OAuth2',
    }


def test_security_requirement_offers_every_scheme_as_an_alternative():
    assert SECURITY_REQUIREMENT == [
        {'ApiKeyAuth': []},
        {'BasicAuth': []},
        {'DigestAuth': []},
        {'OAuth2': ['access_apis']},
    ]


def test_required_permission_read_from_authentication_class():
    resource = FakeResource(
        RequirePermissionAuthentication(HqPermissions.edit_commcare_users)
    )
    assert required_permission(resource) == 'edit_commcare_users'


def test_no_required_permission_for_plain_authentication():
    assert (
        required_permission(FakeResource(LoginAndDomainAuthentication()))
        is None
    )


def test_real_resource_permission():
    from corehq.apps.api.resources import v0_5

    resource = v0_5.CommCareUserResource(api_name='v1')
    assert required_permission(resource) == 'edit_commcare_users'


def test_meta_default_authentication_has_no_permission():
    assert isinstance(CustomResourceMeta.authorization, ReadOnlyAuthorization)
    assert (
        required_permission(FakeResource(CustomResourceMeta.authentication))
        is None
    )
