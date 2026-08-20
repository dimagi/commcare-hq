import re

from django.utils.translation import gettext as _
from oauth2_provider.scopes import SettingsScopes

from corehq.apps.users.models import CouchUser

DOMAIN_SCOPE_PREFIX = 'domain:'
ALL_PROJECTS_SCOPE = ''

class ScopeDescriptions(dict):
    """
    A scope description mapping that synthesizes an entry for any
    ``domain:<name>`` key rather than raising ``KeyError``.

    Only lookup is extended. Iteration and ``items()`` still yield the statically
    configured scopes alone, so a domain scope is described on request but never
    enumerated.
    """

    def __missing__(self, key):
        if key.startswith(DOMAIN_SCOPE_PREFIX):
            domain = key.removeprefix(DOMAIN_SCOPE_PREFIX)
            return _('Access data in the "{}" project space only').format(domain)
        raise KeyError(key)


class HQScopes(SettingsScopes):
    """
    Adds the dynamic ``domain:<name>`` scope to the statically configured scopes.
    Wired up via the ``SCOPES_BACKEND_CLASS`` setting.
    """

    def get_all_scopes(self):
        return ScopeDescriptions(super().get_all_scopes())

    def describe_scopes(self, scopes):
        """
        Descriptions for ``scopes``, skipping any that have none. Each must be
        looked up: checking membership first would report dynamic scopes as absent.
        """
        all_scopes = self.get_all_scopes()
        descriptions = []
        for scope in scopes:
            try:
                descriptions.append(all_scopes[scope])
            except KeyError:
                continue
        return descriptions

    def get_available_scopes(self, application=None, request=None, *args, **kwargs):
        scopes = list(super().get_available_scopes(application, request, *args, **kwargs))
        scopes.extend(self._grantable_domain_scopes(request))
        return scopes

    def _grantable_domain_scopes(self, request):
        if request is None:
            return []
        requested = getattr(request, 'scopes', None) or []
        domains = {
            scope.removeprefix(DOMAIN_SCOPE_PREFIX)
            for scope in requested
            if isinstance(scope, str) and scope.startswith(DOMAIN_SCOPE_PREFIX)
        }
        user = getattr(request, 'user', None)
        return [domain_scope(domain) for domain in domains if self._is_grantable(domain, user)]

    def _is_grantable(self, domain, user):
        from corehq.apps.domain.utils import legacy_domain_re

        if not domain or not re.fullmatch(legacy_domain_re, domain):
            return False
        if user is None:
            # The GET authorize step has no resource owner attached, so membership
            # cannot be checked yet. The consent POST arrives with the real user
            # and re-validates before any Grant row is written.
            return True

        couch_user = CouchUser.from_django_user(user)
        return couch_user is not None and couch_user.is_member_of(domain, allow_enterprise=True)


def token_domains(scope_string):
    """
    Parse the project spaces a token is restricted to out of its raw scope string.
    An empty result means the token is not restricted to any project space.

    >>> sorted(token_domains('access_apis domain:alpha domain:beta'))
    ['alpha', 'beta']
    >>> token_domains('access_apis')
    frozenset()
    """
    if not isinstance(scope_string, str):
        # `access_token` is not always a real token: callers may hold a stand-in
        # without a usable scope. Treat that as unrestricted rather than failing.
        return frozenset()
    return frozenset(
        scope.removeprefix(DOMAIN_SCOPE_PREFIX)
        for scope in scope_string.split()
        if scope.startswith(DOMAIN_SCOPE_PREFIX)
    )


def domain_scope(domain):
    return f'{DOMAIN_SCOPE_PREFIX}{domain}'
