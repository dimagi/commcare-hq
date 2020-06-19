from django.contrib import messages
from django.http import Http404, HttpResponseRedirect
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.translation import ugettext as _

from collections import namedtuple
from memoized import memoized

from corehq.apps.accounting.mixins import BillingModalsMixin
from corehq.apps.domain.decorators import (
    login_and_domain_required,
    login_required,
)
from corehq.apps.domain.models import Domain
from corehq.apps.domain.utils import normalize_domain_name
from corehq.apps.hqwebapp.utils import send_confirmation_email
from corehq.apps.hqwebapp.views import BaseSectionPageView
from corehq.apps.users.models import Invitation
from corehq.apps.domain.middleware import get_last_visited_domain, set_last_visited_domain
from corehq.util.quickcache import quickcache


def covid19(request):
    return select(request, next_view="app_exchange")

# Domain not required here - we could be selecting it for the first time. See notes domain.decorators
# about why we need this custom login_required decorator
@login_required
def select(request, do_not_redirect=False, next_view=None):
    if not hasattr(request, 'couch_user'):
        return redirect('registration_domain')

    # next_view must be a url that expects exactly one parameter, a domain name
    next_view = next_view or request.GET.get('next_view')
    show_invitations = False
    if not next_view:
        next_view = "domain_homepage"
        show_invitations = True
    domain_links = get_domain_links_for_dropdown(request.couch_user, view_name=next_view)
    if not domain_links:
        return redirect('registration_domain')
    domain_links += get_mirror_domain_links_for_dropdown(request.couch_user, view_name=next_view)
    domain_links = sorted(domain_links, key=lambda link: link['display_name'].lower())

    email = request.couch_user.get_email()
    open_invitations = [e for e in Invitation.by_email(email) if not e.is_expired]

    additional_context = {
        'domain_links': domain_links,
        'invitation_links': [{
            'display_name': i.domain,
            'url': reverse("domain_accept_invitation", args=[i.domain, i.uuid]) + '?no_redirect=true',
        } for i in open_invitations] if show_invitations else [],
        'current_page': {'page_name': _('Select A Project')},
    }

    domain_select_template = "domain/select.html"
    last_visited_domain = get_last_visited_domain(request.couch_user)
    if open_invitations \
       or do_not_redirect \
       or not last_visited_domain:
        return render(request, domain_select_template, additional_context)
    else:
        domain_obj = Domain.get_by_name(last_visited_domain)
        if domain_obj and domain_obj.is_active:
            # mirrors logic in login_and_domain_required
            if (
                request.couch_user.is_member_of(domain_obj, allow_mirroring=True)
                or (request.user.is_superuser and not domain_obj.restrict_superusers)
                or domain_obj.is_snapshot
            ):
                try:
                    return HttpResponseRedirect(reverse(next_view or 'dashboard_default',
                                                args=[last_visited_domain]))
                except Http404:
                    pass

        set_last_visited_domain(request.couch_user, None)
        return render(request, domain_select_template, additional_context)


@login_required
def accept_all_invitations(request):
    def _invite(invitation, user):
        user.add_as_web_user(invitation.domain, role=invitation.role,
                             location_id=invitation.supply_point, program_id=invitation.program)
        invitation.is_accepted = True
        invitation.save()
        send_confirmation_email(invitation)

    user = request.couch_user
    invites = Invitation.by_email(user.username)
    for invitation in invites:
        if not invitation.is_expired:
            _invite(invitation, user)
            messages.success(request, _(f'You have been added to the "{invitation.domain}" project space.'))
    return HttpResponseRedirect(reverse('domain_select_redirect'))


@quickcache(['couch_user.username'])
def get_domain_links_for_dropdown(couch_user, view_name="domain_homepage"):
    # Returns dicts with keys 'name', 'display_name', and 'url'
    return _domains_to_links(Domain.active_for_user(couch_user), view_name)


# Returns domains where given user has access only by virtue of a DomainPermissionsMirror
@quickcache(['couch_user.username'])
def get_mirror_domain_links_for_dropdown(couch_user, view_name="domain_homepage"):
    # Returns dicts with keys 'name', 'display_name', and 'url'
    from corehq.apps.users.models import DomainPermissionsMirror
    domain_links_by_name = {d['name']: d for d in get_domain_links_for_dropdown(couch_user)}
    mirror_domain_objects_by_name = {}
    for domain_name in domain_links_by_name:
        for mirror_domain in DomainPermissionsMirror.mirror_domains(domain_name):
            if mirror_domain not in domain_links_by_name:
                mirror_domain_objects_by_name[mirror_domain] = Domain.get_by_name(mirror_domain)

    return _domains_to_links(mirror_domain_objects_by_name.values(), view_name)


def _domains_to_links(domain_objects, view_name):
    return sorted([{
        'name': o.name,
        'display_name': o.display_name(),
        'url': reverse(view_name, args=[o.name]),
    } for o in domain_objects], key=lambda link: link['display_name'].lower())


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
