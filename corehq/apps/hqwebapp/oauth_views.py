from django.utils.decorators import method_decorator

from memoized import memoized
from oauth2_provider.models import get_application_model
from oauth2_provider.scopes import get_scopes_backend
from oauth2_provider.views.base import AuthorizationView

from corehq.apps.domain.models import Domain
from corehq.apps.hqwebapp.decorators import use_bootstrap5
from corehq.apps.hqwebapp.forms import HQAllowForm
from corehq.apps.hqwebapp.oauth_scopes import DOMAIN_SCOPE_PREFIX


@method_decorator(use_bootstrap5, name="dispatch")
class HQAuthorizationView(AuthorizationView):
    """
    The OAuth2 consent screen, extended to ask which project space is being shared.
    """
    urlname = 'oauth_authorize'
    template_name = 'hqwebapp/bootstrap5/oauth_authorize.html'
    form_class = HQAllowForm

    def get(self, request, *args, **kwargs):
        # Disable approval_prompt=auto: it reuses an earlier approval and skips
        # this screen, so a client could replay an authorize URL to get a token
        # that names no project space. Clients should refresh instead.
        request.GET = request.GET.copy()
        request.GET.pop('approval_prompt', None)
        return super().get(request, *args, **kwargs)

    @property
    @memoized
    def domain_choices(self):
        choices = [
            (domain, self._domain_display_name(domain))
            for domain in self.request.couch_user.get_domains(allow_enterprise=True)
        ]
        return sorted(choices, key=lambda choice: choice[1].lower())

    @staticmethod
    def _domain_display_name(domain):
        domain_obj = Domain.get_by_name(domain)
        return domain_obj.display_name() if domain_obj else domain

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['domain_choices'] = self.domain_choices
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        scopes = [
            scope for scope in context.get('scopes') or []
            if not scope.startswith(DOMAIN_SCOPE_PREFIX)
        ]
        context['scopes'] = scopes
        context['scopes_descriptions'] = get_scopes_backend().describe_scopes(scopes)
        return context

    def form_invalid(self, form):
        # The context is built during GET and gone by the time a POST fails, so
        # rebuild it from the hidden fields the form posted back.
        client_id = form.data.get('client_id')
        return self.render_to_response(self.get_context_data(
            form=form,
            application=get_application_model().objects.filter(client_id=client_id).first(),
            client_id=client_id,
            redirect_uri=form.data.get('redirect_uri'),
            response_type=form.data.get('response_type'),
            state=form.data.get('state'),
            scopes=(form.data.get('scope') or '').split(),
        ))
