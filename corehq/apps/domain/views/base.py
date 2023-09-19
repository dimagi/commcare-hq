from django.contrib import messages
from django.http import Http404, HttpResponseRedirect
from django.shortcuts import redirect, render
from django.urls import Resolver404, resolve, reverse
from django.utils.translation import gettext as _

from memoized import memoized

from corehq.apps.accounting.mixins import BillingModalsMixin
from corehq.apps.domain.decorators import LoginAndDomainMixin, login_required
from corehq.apps.domain.models import Domain
from corehq.apps.domain.utils import normalize_domain_name
from corehq.apps.hqwebapp.views import BaseSectionPageView
from corehq.apps.users.models import Invitation


def covid19(request):
    return select(request, get_url=_view_name_to_fn("app_exchange"))


def _view_name_to_fn(view_name):
    def get_url(domain):
        return reverse(view_name, kwargs={'domain': domain})
    return get_url


# Domain not required here - we could be selecting it for the first time. See notes domain.decorators
# about why we need this custom login_required decorator
@login_required
def select(request, always_show_list=False, get_url=None):
    """
    Show list of user's domains and open invitations. Can also redirect to
    specific views and/or auto-select the most recently used domain.

    :param always_show_list: always show list of domains to select (if False,
    automatically go to last used domain)
    :param get_url: function which accepts a domain and returns a URL
    """
    if not hasattr(request, 'couch_user'):
        return redirect('registration_domain')

    show_invitations = False
    if get_url is None:
        show_invitations = True
    domain_links = get_domain_links(request.couch_user, get_url=get_url)
    if not domain_links:
        return redirect('registration_domain')
    domain_links += get_enterprise_links(request.couch_user, get_url=get_url)
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
    last_visited_domain = request.session.get('last_visited_domain')
    if open_invitations \
       or always_show_list \
       or not last_visited_domain:
        return render(request, domain_select_template, additional_context)
    else:
        domain_obj = Domain.get_by_name(last_visited_domain)
        if domain_obj and domain_obj.is_active:
            # mirrors logic in login_and_domain_required
            if (
                request.couch_user.is_member_of(domain_obj, allow_enterprise=True)
                or (request.user.is_superuser and not domain_obj.restrict_superusers)
                or domain_obj.is_snapshot
            ):
                if get_url is not None:
                    url = get_url(last_visited_domain)
                else:
                    url = reverse('domain_homepage', args=[last_visited_domain])
                return HttpResponseRedirect(url)

        del request.session['last_visited_domain']
        return render(request, domain_select_template, additional_context)


@login_required
def accept_all_invitations(request):
    user = request.couch_user
    invites = Invitation.by_email(user.username)
    for invitation in invites:
        if not invitation.is_expired:
            invitation.accept_invitation_and_join_domain(user)
            messages.success(request, _(f'You have been added to the "{invitation.domain}" project space.'))
    return HttpResponseRedirect(reverse('domain_select_redirect'))


def get_domain_links(couch_user, get_url=None):
    return _domains_to_links(Domain.active_for_user(couch_user), get_url)


# Returns domains where given user has access only by virtue of enterprise permissions
def get_enterprise_links(couch_user, get_url=None):
    from corehq.apps.enterprise.models import EnterprisePermissions
    user_domains = {d.name for d in Domain.active_for_user(couch_user)}
    subdomains = {subdomain for domain_name in user_domains
                  for subdomain in EnterprisePermissions.get_domains(domain_name)}
    subdomains -= user_domains
    subdomain_objects = [Domain.get_by_name(d) for d in subdomains]
    return _domains_to_links(subdomain_objects, get_url)


def _domains_to_links(domain_objects, get_url):
    if not get_url:
        get_url = _view_name_to_fn('domain_homepage')
    return sorted([{
        'name': o.name,
        'display_name': o.display_name(),
        'url': get_url(o.name),
    } for o in domain_objects if o], key=lambda link: link['display_name'].lower())


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


def redirect_to_domain(request):
    """Allows us to use eg commcarehq.org/a/DOMAIN/settings/users/web
    in documentation and have it redirect to the user's domain"""
    # switch out the DOMAIN placeholder so it doesn't match this view
    resolvable_path = '/a/example/' + request.path.removeprefix('/a/DOMAIN/')
    try:
        match = resolve(resolvable_path)
    except Resolver404:
        raise Http404()

    def get_url(domain):
        return reverse(match.url_name, kwargs={**match.kwargs, 'domain': domain})
    return select(request, always_show_list=True, get_url=get_url)
