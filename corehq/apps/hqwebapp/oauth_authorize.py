"""OAuth consent screen with a project-space picker.

Replaces django-oauth-toolkit's AuthorizationView so the user can
restrict the grant to one of their project spaces at consent time. The
chosen domain is recorded as a ``domain:<name>`` scope on the grant
(and therefore on the tokens minted from it); "All my project spaces"
preserves the pre-existing behavior of an unrestricted token.
"""
from django import forms
from django.utils.functional import cached_property
from django.utils.translation import gettext_lazy as _

from oauth2_provider.forms import AllowForm
from oauth2_provider.views import AuthorizationView

from corehq.apps.hqwebapp.oauth_scopes import DOMAIN_SCOPE_PREFIX, domain_scope
from corehq.apps.users.models import CouchUser


class DomainScopedAllowForm(AllowForm):
    domain = forms.ChoiceField(
        required=False,
        label=_('Limit access to project space'),
    )

    def __init__(self, *args, user_domains=(), **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['domain'].choices = [
            ('', _('All my project spaces')),
        ] + [(domain, domain) for domain in user_domains]


class HQAuthorizationView(AuthorizationView):
    form_class = DomainScopedAllowForm
    template_name = 'hqwebapp/oauth_authorize.html'

    @cached_property
    def _user_domains(self):
        couch_user = CouchUser.get_by_username(self.request.user.username)
        return couch_user.domains if couch_user else []

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user_domains'] = self._user_domains
        return kwargs

    def get_initial(self):
        # Pre-select a client-requested domain:<name> scope when the user
        # is a member of that domain
        initial = super().get_initial()
        for domain in _domains_from_scope(initial.get('scope')):
            if domain in self._user_domains:
                initial['domain'] = domain
                break
        return initial

    def form_valid(self, form):
        # The picker is the single source of truth for domain scopes:
        # client-requested domain scopes are replaced by the user's choice
        scopes = [
            scope for scope in form.cleaned_data['scope'].split()
            if not scope.startswith(DOMAIN_SCOPE_PREFIX)
        ]
        domain = form.cleaned_data.get('domain')
        if domain:
            scopes.append(domain_scope(domain))
        form.cleaned_data['scope'] = ' '.join(scopes)
        return super().form_valid(form)


def _domains_from_scope(scope):
    return [
        s[len(DOMAIN_SCOPE_PREFIX):]
        for s in (scope or '').split()
        if s.startswith(DOMAIN_SCOPE_PREFIX)
    ]
