from datetime import datetime
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, login
from django.core.urlresolvers import reverse
from django.db import transaction
from django.http import HttpResponseRedirect, Http404
from django.shortcuts import redirect, render
from django.utils.decorators import method_decorator
from django.utils.translation import ugettext as _
import sys

from django.views.generic.base import TemplateView

from corehq.apps.analytics.tasks import (
    track_workflow,
    track_confirmed_account_on_hubspot,
)
from corehq.apps.domain.decorators import login_required
from corehq.apps.domain.models import Domain
from corehq.apps.domain.exceptions import NameUnavailableException
from corehq.apps.registration.models import RegistrationRequest
from corehq.apps.registration.forms import NewWebUserRegistrationForm, DomainRegistrationForm
from corehq.apps.registration.utils import activate_new_user, send_new_request_update_email, request_new_domain, \
    send_domain_registration_email
from corehq.apps.style.decorators import use_bootstrap3_func, use_bootstrap3
from corehq.apps.users.models import WebUser, CouchUser
from dimagi.utils.couch.resource_conflict import retry_resource
from dimagi.utils.web import get_ip
from corehq.util.context_processors import get_per_domain_context

DOMAIN_TYPES = (
    'commcare',
    'commtrack'
)


def get_domain_context(domain_type='commcare'):
    """
    Set context variables that are normally set based on the domain type
    according to what user/domain type is being registered.
    """
    from corehq.apps.domain.utils import get_dummy_domain
    dummy_domain = get_dummy_domain(domain_type)
    return get_per_domain_context(dummy_domain)


def registration_default(request):
    return redirect(register_user)


@transaction.atomic
@use_bootstrap3_func
def register_user(request, domain_type=None):
    domain_type = domain_type or 'commcare'
    if domain_type not in DOMAIN_TYPES:
        raise Http404()

    prefilled_email = request.GET.get('e', '')

    context = get_domain_context(domain_type)

    if request.user.is_authenticated():
        # Redirect to a page which lets user choose whether or not to create a new account
        domains_for_user = Domain.active_for_user(request.user)
        if len(domains_for_user) == 0:
            return redirect("registration_domain", domain_type=domain_type)
        else:
            return redirect("homepage")
    else:
        if request.method == 'POST':
            form = NewWebUserRegistrationForm(request.POST)
            if form.is_valid():
                activate_new_user(form, ip=get_ip(request))
                new_user = authenticate(username=form.cleaned_data['email'],
                                        password=form.cleaned_data['password'])

                track_workflow(new_user.email, "Requested new account")

                login(request, new_user)

                requested_domain = form.cleaned_data['hr_name']
                if form.cleaned_data['create_domain']:
                    try:
                        requested_domain = request_new_domain(
                            request, form, new_user=True, domain_type=domain_type)
                    except NameUnavailableException:
                        context.update({
                            'error_msg': _('Project name already taken - please try another'),
                            'show_homepage_link': 1
                        })
                        return render(request, 'error.html', context)

                context = get_domain_context(form.cleaned_data['domain_type']).update({
                    'alert_message': _("An email has been sent to %s.") % request.user.username,
                    'requested_domain': requested_domain,
                    'track_domain_registration': True,
                })
                return render(request, 'registration/confirmation_sent.html', context)
            context.update({'create_domain': form.cleaned_data['create_domain']})
        else:
            form = NewWebUserRegistrationForm(
                initial={'domain_type': domain_type, 'email': prefilled_email, 'create_domain': True})
            context.update({'create_domain': True})

        context.update({
            'form': form,
            'domain_type': domain_type,
        })
        return render(request, 'registration/create_new_user.html', context)


class RegisterDomainView(TemplateView):
    template_name = 'registration/domain_request.html'

    @method_decorator(login_required)
    @use_bootstrap3
    def dispatch(self, request, *args, **kwargs):
        return super(RegisterDomainView, self).dispatch(request, *args, **kwargs)

    def get(self, request, *args, **kwargs):
        active_domains_for_user = Domain.active_for_user(request.user)
        if len(active_domains_for_user) <= 0 and not request.user.is_superuser:
            domains_for_user = Domain.active_for_user(request.user, is_active=False)
            if len(domains_for_user) > 0:
                context = get_domain_context(kwargs.get('domain_type') or 'commcare')
                context['requested_domain'] = domains_for_user[0]
                return render(request, 'registration/confirmation_waiting.html', context)
        return super(RegisterDomainView, self).get(request, *args, **kwargs)

    @transaction.atomic
    def post(self, request, *args, **kwargs):
        domain_type = kwargs.get('domain_type') or 'commcare'
        is_new = False
        referer_url = request.GET.get('referer', '')
        nextpage = request.POST.get('next')
        form = DomainRegistrationForm(request.POST)
        context = self.get_context_data(form=form)
        if form.is_valid():
            reqs_today = RegistrationRequest.get_requests_today()
            max_req = settings.DOMAIN_MAX_REGISTRATION_REQUESTS_PER_DAY
            if reqs_today >= max_req:
                context.update({
                    'error_msg': _(
                        'Number of domains requested today exceeds limit (%d) - contact Dimagi'
                    ) % max_req,
                    'show_homepage_link': 1
                })
                return render(request, 'error.html', context)

            try:
                domain_name = request_new_domain(
                    request, form, new_user=is_new, domain_type=domain_type)
            except NameUnavailableException:
                context.update({
                    'error_msg': _('Project name already taken - please try another'),
                    'show_homepage_link': 1
                })
                return render(request, 'error.html', context)

            if is_new:
                context.update({
                    'alert_message': _("An email has been sent to %s.") % request.user.username,
                    'requested_domain': domain_name,
                    'track_domain_registration': True,
                })
                return render(request, 'registration/confirmation_sent.html', context)
            else:
                if nextpage:
                    return HttpResponseRedirect(nextpage)
                if referer_url:
                    return redirect(referer_url)
                return HttpResponseRedirect(reverse("domain_homepage", args=[domain_name]))

        return self.render_to_response(context)

    def get_context_data(self, **kwargs):
        request = self.request
        domain_type = kwargs.get('domain_type') or 'commcare'
        if domain_type not in DOMAIN_TYPES or (not request.couch_user) or request.couch_user.is_commcare_user():
            raise Http404()

        context = super(RegisterDomainView, self).get_context_data(**kwargs)
        context .update(get_domain_context(domain_type))
        is_new = False

        active_domains_for_user = Domain.active_for_user(request.user)
        if len(active_domains_for_user) <= 0 and not request.user.is_superuser:
            is_new = True

        context.update({
            'form': kwargs.get('form') or DomainRegistrationForm(initial={'domain_type': domain_type}),
            'is_new': is_new,
        })
        return context


@transaction.atomic
@login_required
def resend_confirmation(request):
    try:
        dom_req = RegistrationRequest.get_request_for_username(request.user.username)
    except Exception:
        dom_req = None
        
    if not dom_req:
        inactive_domains_for_user = Domain.active_for_user(request.user, is_active=False)
        if len(inactive_domains_for_user) > 0:
            for domain in inactive_domains_for_user:
                domain.is_active = True
                domain.save()
        return redirect('domain_select')

    context = get_domain_context(dom_req.project.domain_type)

    if request.method == 'POST':
        try:
            send_domain_registration_email(dom_req.new_user_username,
                    dom_req.domain, dom_req.activation_guid,
                    request.user.get_full_name())
        except Exception:
            context.update({
                'error_msg': _('There was a problem with your request'),
                'error_details': sys.exc_info(),
                'show_homepage_link': 1,
            })
            return render(request, 'error.html', context)
        else:
            context.update({
                'alert_message': _(
                    "An email has been sent to %s.") % dom_req.new_user_username,
                'requested_domain': dom_req.domain
            })
            return render(request, 'registration/confirmation_sent.html',
                context)

    context.update({
        'requested_domain': dom_req.domain
    })
    return render(request, 'registration/confirmation_resend.html', context)


@transaction.atomic
def confirm_domain(request, guid=None):
    error = None
    # Did we get a guid?
    if guid is None:
        error = _('An account activation key was not provided.  If you think this '
                  'is an error, please contact the system administrator.')

    # Does guid exist in the system?
    else:
        req = RegistrationRequest.get_by_guid(guid)
        if not req:
            error = _('The account activation key "%s" provided is invalid. If you '
                      'think this is an error, please contact the system '
                      'administrator.') % guid

    if error is not None:
        context = {
            'message_title': _('Account not activated'),
            'message_subtitle': _('Email not yet confirmed'),
            'message_body': error,
        }
        return render(request, 'registration/confirmation_error.html', context)

    requested_domain = Domain.get_by_name(req.domain)

    # Has guid already been confirmed?
    if requested_domain.is_active:
        assert(req.confirm_time is not None and req.confirm_ip is not None)
        messages.success(request, 'Your account %s has already been activated. '
                                  'No further validation is required.' % req.new_user_username)
        return HttpResponseRedirect(reverse("dashboard_default", args=[requested_domain]))

    # Set confirm time and IP; activate domain and new user who is in the
    req.confirm_time = datetime.utcnow()
    req.confirm_ip = get_ip(request)
    req.save()
    requested_domain.is_active = True
    requested_domain.save()
    requesting_user = WebUser.get_by_username(req.new_user_username)

    send_new_request_update_email(requesting_user, get_ip(request), requested_domain.name, is_confirming=True)

    messages.success(
        request, 'Your account has been successfully activated.  Thank you for taking '
                 'the time to confirm your email address: %s.' % requesting_user.username)
    track_workflow(requesting_user.email, "Confirmed new project")
    track_confirmed_account_on_hubspot.delay(requesting_user)
    return HttpResponseRedirect(reverse("dashboard_default", args=[requested_domain]))


@retry_resource(3)
def eula_agreement(request):
    if request.method == 'POST':
        current_user = CouchUser.from_django_user(request.user)
        current_user.eula.signed = True
        current_user.eula.date = datetime.utcnow()
        current_user.eula.user_ip = get_ip(request)
        current_user.save()

    return HttpResponseRedirect(request.POST.get('next', '/'))
