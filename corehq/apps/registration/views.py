from datetime import datetime
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, login
from django.db import transaction
from django.forms.forms import Form
from django.http import HttpResponseRedirect
from django.shortcuts import redirect
from corehq.apps.domain.decorators import login_required_late_eval_of_LOGIN_URL
from corehq.apps.domain.models import Domain
from corehq.apps.orgs.views import orgs_landing
from corehq.apps.registration.models import RegistrationRequest
from corehq.apps.registration.forms import NewWebUserRegistrationForm, DomainRegistrationForm, OrganizationRegistrationForm
from corehq.apps.registration.utils import *
from dimagi.utils.couch.resource_conflict import retry_resource
from dimagi.utils.web import render_to_response, get_ip
from corehq.apps.domain.decorators import require_superuser
from corehq.apps.orgs.models import Organization

@transaction.commit_on_success
def register_user(request):
    if request.user.is_authenticated():
        # Redirect to a page which lets user choose whether or not to create a new account
        vals = {}
        domains_for_user = Domain.active_for_user(request.user)
        if len(domains_for_user) == 0:
            return redirect("registration_domain")
        else:
            return redirect("domain_list")
    else:
        if request.method == 'POST': # If the form has been submitted...
            form = NewWebUserRegistrationForm(request.POST) # A form bound to the POST data
            if form.is_valid(): # All validation rules pass
                activate_new_user(form, ip=get_ip(request))
                new_user = authenticate(username=form.cleaned_data['email'],
                                        password=form.cleaned_data['password'])
                login(request, new_user)

                return redirect('registration_domain')
        else:
            form = NewWebUserRegistrationForm() # An unbound form

        vals = dict(form = form)
        return render_to_response(request, 'registration/create_new_user.html', vals)

@require_superuser
@transaction.commit_on_success
@login_required_late_eval_of_LOGIN_URL
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
            logo = form.cleaned_data["logo"]
            if logo:
                logo_filename = logo.name
            else:
                logo_filename = ''

            org = Organization(name=name, title=title, location=location, email=email, url=url, logo_filename=logo_filename)
            org.save()
            if logo:
                org.put_attachment(content=logo.read(), name=logo.name)

            if referer_url:
                return redirect(referer_url)
            return HttpResponseRedirect(reverse("orgs_landing", args=[name]))
    else:
        form = OrganizationRegistrationForm() # An unbound form

    vals = dict(form=form)
    return render_to_response(request, template, vals)



@transaction.commit_on_success
@login_required_late_eval_of_LOGIN_URL
def register_domain(request):
    is_new = False
    referer_url = request.GET.get('referer', '')

    active_domains_for_user = Domain.active_for_user(request.user)
    if len(active_domains_for_user) <= 0 and not request.user.is_superuser:
        is_new = True
        domains_for_user = Domain.active_for_user(request.user, is_active=False)
        if len(domains_for_user) > 0:
            vals = dict(requested_domain=domains_for_user[0])
            return render_to_response(request, 'registration/confirmation_waiting.html', vals)

    if request.method == 'POST': # If the form has been submitted...
        nextpage = request.POST.get('next')
        org = request.POST.get('org')
        form = DomainRegistrationForm(request.POST) # A form bound to the POST data
        if form.is_valid(): # All validation rules pass
            reqs_today = RegistrationRequest.get_requests_today()
            max_req = settings.DOMAIN_MAX_REGISTRATION_REQUESTS_PER_DAY
            if reqs_today >= max_req:
                vals = {'error_msg':'Number of domains requested today exceeds limit ('+str(max_req)+') - contact Dimagi',
                        'show_homepage_link': 1 }
                return render_to_response(request, 'error.html', vals)

            request_new_domain(request, form, org, is_new)
            requested_domain = form.cleaned_data['domain_name']
            if is_new:
                vals = dict(alert_message="An email has been sent to %s." % request.user.username, requested_domain=requested_domain)
                return render_to_response(request, 'registration/confirmation_sent.html', vals)
            else:
                messages.success(request, '<strong>The project {project_name} was successfully created!</strong> An email has been sent to {username} for your records.'.format(
                    username=request.user.username,
                    project_name=requested_domain
                ), extra_tags="html")

                if nextpage:
                    return HttpResponseRedirect(nextpage)
                if referer_url:
                    return redirect(referer_url)
                return HttpResponseRedirect(reverse("domain_homepage", args=[requested_domain]))
        else:
            if nextpage:
#                messages.error(request, "The new project could not be created! Please make sure to fill out all fields of the form.")
                return orgs_landing(request, org, form=form)
    else:
        form = DomainRegistrationForm() # An unbound form

    vals = dict(form=form, is_new=is_new)

    return render_to_response(request, 'registration/domain_request.html', vals)

@transaction.commit_on_success
@login_required_late_eval_of_LOGIN_URL
def resend_confirmation(request):
    dom_req = None
    try:
        dom_req = RegistrationRequest.get_request_for_username(request.user.username)
    except Exception:
        pass


    if not dom_req:
        inactive_domains_for_user = Domain.active_for_user(request.user, is_active=False)
        if len(inactive_domains_for_user) > 0:
            for domain in inactive_domains_for_user:
                domain.is_active = True
                domain.save()
        return redirect('domain_select')

    if request.method == 'POST': # If the form has been submitted...
        try:
            send_domain_registration_email(dom_req.new_user_username, dom_req.domain, dom_req.activation_guid)
        except Exception:
            vals = {'error_msg':'There was a problem with your request',
                    'error_details':sys.exc_info(),
                    'show_homepage_link': 1 }
            return render_to_response(request, 'error.html', vals)
        else:
            vals = dict(alert_message="An email has been sent to %s." % dom_req.new_user_username, requested_domain=dom_req.domain)
            return render_to_response(request, 'registration/confirmation_sent.html', vals)

    vals = dict(requested_domain=dom_req.domain)
    return render_to_response(request, 'registration/confirmation_resend.html', vals)

@transaction.commit_on_success
def confirm_domain(request, guid=None):
    # Did we get a guid?
    vals = {}
    if guid is None:
        vals['message_title'] = 'Missing Activation Key'
        vals['message_subtitle'] = 'Account Activation Failed'
        vals['message_body'] = 'An account activation key was not provided. If you think this is an error, please contact the system administrator.'
        vals['is_error'] = True
        return render_to_response(request, 'registration/confirmation_complete.html', vals)

    # Does guid exist in the system?
    req = RegistrationRequest.get_by_guid(guid)
    if not req:
        vals['message_title'] = 'Invalid Activation Key'
        vals['message_subtitle'] = 'Account Activation Failed'
        vals['message_body'] = 'The account activation key "%s" provided is invalid. If you think this is an error, please contact the system administrator.'  % guid
        vals['is_error'] = True
        return render_to_response(request, 'registration/confirmation_complete.html', vals)

    # Has guid already been confirmed?
    vals['requested_domain'] = req.domain
    requested_domain = Domain.get_by_name(req.domain)
    if requested_domain.is_active:
        assert(req.confirm_time is not None and req.confirm_ip is not None)
        vals['message_title'] = 'Already Activated'
        vals['message_body'] = 'Your account %s has already been activated. No further validation is required.' % req.new_user_username
        vals['is_error'] = False
        return render_to_response(request, 'registration/confirmation_complete.html', vals)

    # Set confirm time and IP; activate domain and new user who is in the
    req.confirm_time = datetime.utcnow()
    req.confirm_ip = get_ip(request)
    req.save()
    requested_domain.is_active = True
    requested_domain.save()
    requesting_user = WebUser.get_by_username(req.new_user_username)

    send_new_domain_request_update_email(requesting_user, get_ip(request), requested_domain.name, is_confirming=True)

    vals['message_title'] = 'Account Confirmed'
    vals['message_subtitle'] = 'Thank you for activating your account, %s!' % requesting_user.first_name
    vals['message_body'] = 'Your account has been successfully activated. Thank you for taking the time to confirm your email address: %s.' % requesting_user.username
    vals['is_error'] = False
    return render_to_response(request, 'registration/confirmation_complete.html', vals)

@retry_resource(3)
def eula_agreement(request):
    if request.method == 'POST':
        current_user = CouchUser.from_django_user(request.user)
        current_user.eula.signed = True
        current_user.eula.date = datetime.utcnow()
        current_user.eula.type = 'End User License Agreement'
        current_user.eula.user_ip = get_ip(request)
        current_user.save()

    return HttpResponseRedirect(request.POST.get('next', '/'))