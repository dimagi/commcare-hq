"""Dynamic OAuth scopes for HQ.

In addition to the static scopes in ``settings.OAUTH2_PROVIDER['SCOPES']``,
HQ supports ``domain:<name>`` scopes that restrict an access token to
specific project spaces. They are dynamic (one per domain), so they can't
be enumerated in settings; this backend accepts whatever ``domain:*``
scopes a request asks for and describes them for the consent screen.

Holding a ``domain:<x>`` scope never *grants* access to x — enforcement
in ``corehq.apps.domain.decorators`` only ever narrows what the user
could already do, so accepting arbitrary requested domain scopes here is
safe.
"""
from oauth2_provider.scopes import SettingsScopes

DOMAIN_SCOPE_PREFIX = 'domain:'


def domain_scope(domain):
    return f'{DOMAIN_SCOPE_PREFIX}{domain}'


class _ScopeDescriptions(dict):
    """Dict of scope -> description that can describe any domain scope."""

    def __missing__(self, scope):
        if scope.startswith(DOMAIN_SCOPE_PREFIX):
            domain = scope[len(DOMAIN_SCOPE_PREFIX):]
            return f"Limit access to the '{domain}' project space only"
        raise KeyError(scope)


class HQScopes(SettingsScopes):

    def get_all_scopes(self):
        return _ScopeDescriptions(super().get_all_scopes())

    def get_available_scopes(self, application=None, request=None, *args, **kwargs):
        available = list(super().get_available_scopes(
            application, request, *args, **kwargs))
        requested = getattr(request, 'scopes', None) or []
        available.extend(
            scope for scope in requested
            if scope.startswith(DOMAIN_SCOPE_PREFIX) and scope not in available
        )
        return available
