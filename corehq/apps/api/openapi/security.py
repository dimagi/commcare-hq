"""Authentication schemes and permissions for the generated specs.

``corehq.apps.domain.decorators.api_auth`` accepts API key, Basic, Digest,
session and OAuth2 credentials. Session authentication is deliberately not
described: it is for the web UI, not for API clients.
"""

API_KEY_DESCRIPTION = (
    'Send the header `Authorization: ApiKey <username>:<api_key>`. '
    'Generate an API key from your CommCare HQ account settings.'
)

SECURITY_SCHEMES = {
    'ApiKeyAuth': {
        'type': 'apiKey',
        'in': 'header',
        'name': 'Authorization',
        'description': API_KEY_DESCRIPTION,
    },
    'BasicAuth': {
        'type': 'http',
        'scheme': 'basic',
        'description': 'HTTP Basic authentication with a CommCare HQ '
        'username and password.',
    },
    'DigestAuth': {
        'type': 'http',
        'scheme': 'digest',
        'description': 'HTTP Digest authentication with a CommCare HQ '
        'username and password.',
    },
    'OAuth2': {
        'type': 'oauth2',
        'description': 'OAuth2 with the `access_apis` scope.',
        'flows': {
            'authorizationCode': {
                'authorizationUrl': '/oauth/authorize/',
                'tokenUrl': '/oauth/token/',
                'scopes': {'access_apis': 'Access the CommCare APIs'},
            },
        },
    },
}

SECURITY_REQUIREMENT = [
    {'ApiKeyAuth': []},
    {'BasicAuth': []},
    {'DigestAuth': []},
    {'OAuth2': ['access_apis']},
]



def enforces_authentication(resource):
    """Whether the resource's authentication class checks anything at all.

    Tastypie's base ``Authentication.is_authenticated`` returns True for
    every request, so a resource whose authentication does not override it
    authenticates nobody. ``SingleSignOnResource`` is the case in point: it
    verifies a username and password inside ``post_list`` and deliberately
    accepts anonymous requests to do so.

    Publishing the document-wide security requirement for such an operation
    tells an integrator to send an API key that is neither required nor
    checked, and hides the fact that the endpoint is reachable anonymously.
    Derived from the class rather than declared per resource so that the
    next resource to authenticate nobody cannot forget to say so.
    """
    from tastypie.authentication import Authentication

    authentication = getattr(resource._meta, 'authentication', None)
    if authentication is None:
        return False
    return (
        type(authentication).is_authenticated
        is not Authentication.is_authenticated
    )


def required_permission(resource):
    """The permission the resource's authentication class requires, if any."""
    authentication = getattr(resource._meta, 'authentication', None)
    permission = getattr(authentication, 'permission', None)
    if permission is None:
        return None
    return getattr(permission, 'name', str(permission))
