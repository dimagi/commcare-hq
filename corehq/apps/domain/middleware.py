from django.template.response import TemplateResponse
from django.utils.deprecation import MiddlewareMixin

from dimagi.utils.couch.cache import cache_core

from corehq.apps.accounting.models import DefaultProductPlan, Subscription
from corehq.toggles import DATA_MIGRATION


class CCHQPRBACMiddleware(MiddlewareMixin):
    """
    MiddleWare to add request.role based on user or domain
    information. This _must_ be placed after the
    UserMiddleWare if you want it to find the domain and user
    on the request object.

    Note that because the domain comes from the view kwargs, these are all
    'process_view' middleware classes.

    Also note that this is, for now, used only for domain/plan privileges
    so request.role is the Role for the domain's plan, not for the user.
    Neither domains nor users currently have roles in the PRBAC tables.
    """

    def process_view(self, request, view_func, view_args, view_kwargs):
        self.apply_prbac(request)
        return None

    @classmethod
    def apply_prbac(cls, request):
        subscription = (
            Subscription.get_active_subscription_by_domain(request.domain)
            if hasattr(request, 'domain') else None
        )
        if subscription:
            plan_version = subscription.plan_version
            request.role = plan_version.role
            request.plan = plan_version
            request.subscription = subscription
        else:
            plan_version = DefaultProductPlan.get_default_plan_version()
            request.role = plan_version.role
            request.plan = plan_version


class DomainHistoryMiddleware(MiddlewareMixin):

    def process_response(self, request, response):
        if hasattr(request, 'domain') and getattr(response, '_remember_domain', True):
            self.remember_domain_visit(request)
        return response

    def remember_domain_visit(self, request):
        if hasattr(request, 'couch_user') and request.couch_user:
            set_last_visited_domain(request.couch_user, request.domain)


def get_last_visited_domain(couch_user):
    client = cache_core.get_redis_client()
    return client.get(_last_visited_domain_cache_key(couch_user))


def set_last_visited_domain(couch_user, domain):
    client = cache_core.get_redis_client()
    cache_expiration = 60 * 60 * 24 * 7
    cache_key = _last_visited_domain_cache_key(couch_user)
    client.set(cache_key, domain, timeout=cache_expiration)


def _last_visited_domain_cache_key(couch_user):
    return 'last-visited-domain-%s' % couch_user.username


class DomainMigrationMiddleware(MiddlewareMixin):
    """
    Redirects web requests to a page explaining a data migration is occurring
    """

    def process_view(self, request, view_func, view_args, view_kwargs):
        if hasattr(request, 'domain') and hasattr(request, 'couch_user'):
            if getattr(view_func, 'domain_migration_handled', False):
                return None
            if DATA_MIGRATION.enabled(request.domain):
                return TemplateResponse(
                    request=request,
                    template='domain/data_migration_in_progress.html',
                    status=503,
                    context={
                        'domain': request.domain
                    }
                )
        return None
