# Use modern Python
from __future__ import unicode_literals, print_function, absolute_import

# External imports
from django.utils.decorators import method_decorator
from django.views.decorators.debug import sensitive_post_parameters
from corehq.apps.domain.models import Domain
from corehq.apps.domain.utils import normalize_domain_name
from corehq.apps.accounting.exceptions import AccountingError
from corehq.apps.accounting.models import Subscription
from django_prbac.models import Role


class CCHQPRBACMiddleware(object):
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

    @method_decorator(sensitive_post_parameters('password'))
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
        try:
            request.role = Role.objects.get(slug='community_plan_v0')
        except Role.DoesNotExist:
            request.role = Role()  # A fresh Role() has no privileges


class DomainHistoryMiddleware(object):

    def process_response(self, request, response):
        if hasattr(request, 'domain'):
            self.remember_domain_visit(request, response)
        return response

    def remember_domain_visit(self, request, response):
        last_visited_domain = request.session.get('last_visited_domain')
        if last_visited_domain != request.domain:
            request.session['last_visited_domain'] = request.domain


class ProjectMiddleware(object):

    def process_view(self, request, view_func, view_args, view_kwargs):
        """
        Add domain, project, and org properties (if applicable) to request object
        """
        if 'domain' in view_kwargs:
            request.domain = view_kwargs['domain']
            project = Domain.get_by_name(normalize_domain_name(request.domain))
            request.project = project
        if 'org' in view_kwargs:
            request.org = view_kwargs['org']
