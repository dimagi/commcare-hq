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


def test_sso_is_recognised_as_authenticating_nobody():
    """SingleSignOnResource verifies credentials inside post_list and
    accepts anonymous requests to do so, so publishing the document-wide
    security requirement for it would be a false statement."""
    from corehq.apps.api.openapi.security import enforces_authentication
    from corehq.apps.api.resources.v0_4 import SingleSignOnResource

    assert not enforces_authentication(SingleSignOnResource())


def test_a_resource_with_real_authentication_enforces_it():
    from corehq.apps.api.openapi.security import enforces_authentication
    from corehq.apps.api.resources.v0_5 import CommCareUserResource

    assert enforces_authentication(CommCareUserResource())


def test_only_sso_publishes_an_empty_security_requirement():
    """The *set* of unauthenticated operations, not just the mechanism.

    ``security: []`` is OpenAPI's explicit "this operation needs none",
    published wherever ``enforces_authentication()`` returns False. The
    tests above prove that function answers correctly for two resources;
    this one pins the answer across every generated document, so a
    resource that stops enforcing authentication -- by gaining an
    ``Authentication`` subclass that does not override
    ``is_authenticated``, say -- cannot start advertising itself as open
    without this failing.

    Only ``SingleSignOnResource``'s POST qualifies today: it verifies
    credentials inside ``post_list`` and must accept an anonymous request
    in order to do so.
    """
    from corehq.apps.api.openapi.builder import build_all

    unauthenticated = {
        (slug, path, method)
        for slug, document in build_all().items()
        for path, item in document.get('paths', {}).items()
        for method, operation in item.items()
        if method != 'parameters' and operation.get('security') == []
    }
    assert unauthenticated == {
        ('sso-v1', '/a/{domain}/api/sso/v1/', 'post'),
        ('bundle', '/a/{domain}/api/sso/v1/', 'post'),
    }
