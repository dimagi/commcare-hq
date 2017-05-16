# Use modern Python
from __future__ import unicode_literals, print_function, absolute_import

from django.template.response import TemplateResponse

# External imports
from django.utils.deprecation import MiddlewareMixin
from corehq.apps.accounting.exceptions import AccountingError
from corehq.apps.accounting.models import Subscription
from corehq.toggles import DATA_MIGRATION
from django_prbac.models import Role


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
        if hasattr(request, 'domain'):
            try:
                plan_version, subscription = Subscription.get_subscribed_plan_by_domain(request.domain)
                request.role = plan_version.role
                request.plan = plan_version
                request.subscription = subscription
                return None
            except AccountingError:
                pass
        privilege = Role.get_privilege('community_plan_v1')
        if privilege is not None:
            request.role = privilege.role
        else:
            request.role = Role()  # A fresh Role() has no privileges


class DomainHistoryMiddleware(MiddlewareMixin):

    def process_response(self, request, response):
        if hasattr(request, 'domain'):
            self.remember_domain_visit(request, response)
        return response

    def remember_domain_visit(self, request, response):
        last_visited_domain = request.session.get('last_visited_domain')
        if last_visited_domain != request.domain:
            request.session['last_visited_domain'] = request.domain


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
                )
        return None
