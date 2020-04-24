from django.http import Http404, HttpResponseRedirect
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.translation import ugettext as _

from memoized import memoized

from corehq.apps.accounting.mixins import BillingModalsMixin
from corehq.apps.domain.decorators import (
    login_and_domain_required,
    login_required,
)
from corehq.apps.domain.models import Domain
from corehq.apps.domain.utils import normalize_domain_name
from corehq.apps.hqwebapp.views import BaseSectionPageView
from corehq.apps.users.models import SQLInvitation


def covid19(request):
    return select(request, next_view="app_exchange")

# Domain not required here - we could be selecting it for the first time. See notes domain.decorators
# about why we need this custom login_required decorator
@login_required
def select(request, do_not_redirect=False, next_view=None):
    domains_for_user = Domain.active_for_user(request.user)
    if not domains_for_user:
        return redirect('registration_domain')

    email = request.couch_user.get_email()
    open_invitations = [e for e in SQLInvitation.by_email(email) if not e.is_expired]

    # next_view must be a url that expects exactly one parameter, a domain name
    next_view = next_view or request.GET.get('next_view')
    additional_context = {
        'domains_for_user': domains_for_user,
        'open_invitations': [] if next_view else open_invitations,
        'current_page': {'page_name': _('Select A Project')},
        'next_view': next_view or 'domain_homepage',
        'hide_create_new_project': bool(next_view),
    }

    domain_select_template = "domain/select.html"
    last_visited_domain = request.session.get('last_visited_domain')
    if open_invitations \
       or do_not_redirect \
       or not last_visited_domain:
        return render(request, domain_select_template, additional_context)
    else:
        domain_obj = Domain.get_by_name(last_visited_domain)
        if domain_obj and domain_obj.is_active:
            # mirrors logic in login_and_domain_required
            if (
                request.couch_user.is_member_of(domain_obj)
                or (request.user.is_superuser and not domain_obj.restrict_superusers)
                or domain_obj.is_snapshot
            ):
                try:
                    return HttpResponseRedirect(reverse(next_view or 'dashboard_default',
                                                args=[last_visited_domain]))
                except Http404:
                    pass

        del request.session['last_visited_domain']
        return render(request, domain_select_template, additional_context)


class DomainViewMixin(object):
    """
        Paving the way for a world of entirely class-based views.
        Let's do this, guys. :-)

        Set strict_domain_fetching to True in subclasses to bypass the cache.
    """
    strict_domain_fetching = False

    @property
    @memoized
    def domain(self):
        domain = self.args[0] if len(self.args) > 0 else self.kwargs.get('domain', "")
        return normalize_domain_name(domain)

    @property
    @memoized
    def domain_object(self):
        domain_obj = Domain.get_by_name(self.domain, strict=self.strict_domain_fetching)
        if not domain_obj:
            raise Http404()
        return domain_obj


class LoginAndDomainMixin(object):

    @method_decorator(login_and_domain_required)
    def dispatch(self, *args, **kwargs):
        return super(LoginAndDomainMixin, self).dispatch(*args, **kwargs)


class BaseDomainView(LoginAndDomainMixin, BillingModalsMixin, BaseSectionPageView, DomainViewMixin):

    @property
    def main_context(self):
        main_context = super(BaseDomainView, self).main_context
        main_context.update({
            'domain': self.domain,
        })
        return main_context

    @property
    @memoized
    def page_url(self):
        if self.urlname:
            return reverse(self.urlname, args=[self.domain])
