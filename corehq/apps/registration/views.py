from datetime import datetime
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, login
from django.core.urlresolvers import reverse
from django.db import transaction
from django.http import HttpResponseRedirect, Http404
from django.shortcuts import redirect, render
from django.template.loader import render_to_string
from django.utils.translation import ugettext as _
import sys

from corehq.apps.domain.decorators import login_required
from corehq.apps.domain.models import Domain
from corehq.apps.orgs.views import orgs_landing
from corehq.apps.registration.models import RegistrationRequest
from corehq.apps.registration.forms import NewWebUserRegistrationForm, DomainRegistrationForm, OrganizationRegistrationForm
from corehq.apps.registration.utils import activate_new_user, send_new_request_update_email, request_new_domain, \
    send_domain_registration_email
from corehq.apps.users.models import WebUser, CouchUser
from dimagi.utils.couch.resource_conflict import retry_resource
from dimagi.utils.web import get_ip
from corehq.apps.orgs.models import Organization
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

@transaction.commit_on_success
def register_user(request, domain_type=None):
    domain_type = domain_type or 'commcare'
    if domain_type not in DOMAIN_TYPES:
        raise Http404()

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
                login(request, new_user)
                return redirect(
                    'registration_domain', domain_type=domain_type)
        else:
            form = NewWebUserRegistrationForm(
                    initial={'domain_type': domain_type})

        context.update({
            'form': form,
            'domain_type': domain_type
        })
        return render(request, 'registration/create_new_user.html', context)


@transaction.commit_on_success
@login_required
def register_org(request, template="registration/org_request.html"):
    referer_url = request.GET.get('referer', '')
    if request.method == "POST":
        form = OrganizationRegistrationForm(request.POST, request.FILES)
        if form.is_valid():
            name = form.cleaned_data["org_name"]
            title = form.cleaned_data["org_title"]
            email = form.cleaned_data["email"]
            url = form.cleaned_data["url"]
            location = form.cleaned_data["location"]

            org = Organization(name=name, title=title, location=location, email=email, url=url)
            org.save()

            request.couch_user.add_org_membership(org.name, is_admin=True)
            request.couch_user.save()

            send_new_request_update_email(request.couch_user, get_ip(request), org.name, entity_type="org")

            if referer_url:
                return redirect(referer_url)
            messages.info(request, render_to_string('orgs/partials/landing_notification.html',
                                                       {"org": org, "user": request.couch_user}), extra_tags="html")
            return HttpResponseRedirect(reverse("orgs_landing", args=[name]))
    else:
        form = OrganizationRegistrationForm()

    return render(request, template, {
        'form': form,
    })


@transaction.commit_on_success
@login_required
def register_domain(request, domain_type=None):
    domain_type = domain_type or 'commcare'
    if domain_type not in DOMAIN_TYPES or request.couch_user.is_commcare_user():
        raise Http404()

    context = get_domain_context(domain_type)

    is_new = False
    referer_url = request.GET.get('referer', '')

    active_domains_for_user = Domain.active_for_user(request.user)
    if len(active_domains_for_user) <= 0 and not request.user.is_superuser:
        is_new = True
        domains_for_user = Domain.active_for_user(request.user, is_active=False)
        if len(domains_for_user) > 0:
            context['requested_domain'] = domains_for_user[0]
            return render(request, 'registration/confirmation_waiting.html',
                    context)

    if request.method == 'POST':
        nextpage = request.POST.get('next')
        org = request.POST.get('org')
        form = DomainRegistrationForm(request.POST)
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

            request_new_domain(
                request, form, org, new_user=is_new, domain_type=domain_type)

            requested_domain = form.cleaned_data['domain_name']
            if is_new:
                context.update({
                    'alert_message': _("An email has been sent to %s.") % request.user.username,
                    'requested_domain': requested_domain
                })
                return render(request, 'registration/confirmation_sent.html',
                        context)
            else:
                messages.success(request, _(
                    '<strong>The project {project} was successfully created!</strong> '
                    'An email has been sent to {user} for your records.').format(
                    project=requested_domain, user=request.user.username),
                    extra_tags="html")

                if nextpage:
                    return HttpResponseRedirect(nextpage)
                if referer_url:
                    return redirect(referer_url)
                return HttpResponseRedirect(reverse("domain_homepage", args=[requested_domain]))
        else:
            if nextpage:
                return orgs_landing(request, org, form=form)
    else:
        form = DomainRegistrationForm(initial={'domain_type': domain_type})

    context.update({
        'form': form,
        'is_new': is_new,
    })
    return render(request, 'registration/domain_request.html', context)

@transaction.commit_on_success
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
            send_domain_registration_email(dom_req.new_user_username, dom_req.domain, dom_req.activation_guid)
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

@transaction.commit_on_success
def confirm_domain(request, guid=None):
    # Did we get a guid?
    vals = {}
    if guid is None:
        vals['message_title'] = _('Missing Activation Key')
        vals['message_subtitle'] = _('Account Activation Failed')
        vals['message_body'] = _(
            'An account activation key was not provided.  If you think this '
            'is an error, please contact the system administrator.'
        )
        vals['is_error'] = True
        return render(request, 'registration/confirmation_complete.html', vals)

    # Does guid exist in the system?
    req = RegistrationRequest.get_by_guid(guid)
    if not req:
        vals['message_title'] = _('Invalid Activation Key')
        vals['message_subtitle'] = _('Account Activation Failed')
        vals['message_body'] = _(
            'The account activation key "%s" provided is invalid. If you '
            'think this is an error, please contact the system '
            'administrator.'
        ) % guid
        vals['is_error'] = True
        return render(request, 'registration/confirmation_complete.html', vals)

    requested_domain = Domain.get_by_name(req.domain)
    context = get_domain_context(requested_domain.domain_type)
    context['requested_domain'] = req.domain

    # Has guid already been confirmed?
    if requested_domain.is_active:
        assert(req.confirm_time is not None and req.confirm_ip is not None)
        context['message_title'] = _('Already Activated')
        context['message_body'] = _(
            'Your account %s has already been activated. No further '
            'validation is required.'
        ) % req.new_user_username
        context['is_error'] = False
        return render(request, 'registration/confirmation_complete.html',
                context)

    # Set confirm time and IP; activate domain and new user who is in the
    req.confirm_time = datetime.utcnow()
    req.confirm_ip = get_ip(request)
    req.save()
    requested_domain.is_active = True
    requested_domain.save()
    requesting_user = WebUser.get_by_username(req.new_user_username)

    send_new_request_update_email(requesting_user, get_ip(request), requested_domain.name, is_confirming=True)

    context['message_title'] = _('Account Confirmed')
    context['message_subtitle'] = _(
        'Thank you for activating your account, %s!'
    ) % requesting_user.first_name
    context['message_body'] = _(
        'Your account has been successfully activated.  Thank you for taking '
        'the time to confirm your email address: %s.'
    ) % requesting_user.username 
    context['is_error'] = False
    return render(request, 'registration/confirmation_complete.html', context)

@retry_resource(3)
def eula_agreement(request):
    if request.method == 'POST':
        current_user = CouchUser.from_django_user(request.user)
        current_user.eula.signed = True
        current_user.eula.date = datetime.utcnow()
        current_user.eula.user_ip = get_ip(request)
        current_user.save()

    return HttpResponseRedirect(request.POST.get('next', '/'))
