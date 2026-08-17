"""OAuth consent screen with a project-space picker.

Replaces django-oauth-toolkit's AuthorizationView so the user can
restrict the grant to one of their project spaces at consent time. The
chosen domain is recorded as a ``domain:<name>`` scope on the grant
(and therefore on the tokens minted from it); "All my project spaces"
preserves the pre-existing behavior of an unrestricted token.
"""
from django import forms
from django.utils.translation import gettext_lazy as _

from oauth2_provider.forms import AllowForm
from oauth2_provider.views import AuthorizationView

from corehq.apps.hqwebapp.oauth_scopes import domain_scope
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

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        couch_user = CouchUser.get_by_username(self.request.user.username)
        kwargs['user_domains'] = couch_user.domains if couch_user else []
        return kwargs

    def form_valid(self, form):
        domain = form.cleaned_data.get('domain')
        if domain:
            form.cleaned_data['scope'] += f' {domain_scope(domain)}'
        return super().form_valid(form)
