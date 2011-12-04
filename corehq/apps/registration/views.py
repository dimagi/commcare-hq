from datetime import datetime
from django.conf import settings
from django.contrib.auth import authenticate, login
from django.db import transaction
from django.shortcuts import redirect
from corehq.apps.domain.decorators import login_required_late_eval_of_LOGIN_URL
from corehq.apps.domain.models import RegistrationRequest, Domain
from corehq.apps.registration.forms import NewWebUserRegistrationForm, FirstTimeDomainRegistrationForm, ResendConfirmationEmailForm
from corehq.apps.registration.utils import *
from dimagi.utils.web import render_to_response

@transaction.commit_on_success
def register_user(request):
    if request.user.is_authenticated():
        # Redirect to a page which lets user choose whether or not to create a new account
        vals = {}
        domains_for_user = Domain.active_for_user(request.user)
        if len(domains_for_user) == 0:
            return redirect("registration_first_time_domain")
        else:
            return redirect("domain_list")
    else:
        if request.method == 'POST': # If the form has been submitted...
            form = NewWebUserRegistrationForm(request.POST) # A form bound to the POST data
            if form.is_valid(): # All validation rules pass
                activate_new_user(form)
                new_user = authenticate(username=form.cleaned_data['email'],
                                        password=form.cleaned_data['password'])
                login(request, new_user)

                return redirect('registration_first_time_domain')
        else:
            form = NewWebUserRegistrationForm() # An unbound form

        vals = dict(form = form)
        return render_to_response(request, 'registration/new_user.html', vals)


@transaction.commit_on_success
@login_required_late_eval_of_LOGIN_URL
def register_domain(request):

    active_domains_for_user = Domain.active_for_user(request.user)
    if len(active_domains_for_user) > 0:
        return redirect("domain_select")

    domains_for_user = Domain.all_for_user(request.user)
    if len(domains_for_user) > 0:
        vals = dict(requested_domain=domains_for_user[0])
        return render_to_response(request, 'registration/waiting_confirmation.html', vals)

    if request.method == 'POST': # If the form has been submitted...
        form = FirstTimeDomainRegistrationForm(request.POST) # A form bound to the POST data
        if form.is_valid(): # All validation rules pass

            now = datetime.utcnow()
            reqs_today = RegistrationRequest.objects.filter(request_time__gte = now.date()).count()
            max_req = settings.DOMAIN_MAX_REGISTRATION_REQUESTS_PER_DAY
            if reqs_today >= max_req:
                vals = {'error_msg':'Number of domains requested today exceeds limit ('+str(max_req)+') - contact Dimagi',
                        'show_homepage_link': 1 }
                return render_to_response(request, 'error.html', vals)

            request_new_domain(request, form)

            vals = dict(alert_message="Thank you for requesting the domain %s on CommCare HQ." % form.cleaned_data['domain_name'])
            return render_to_response(request, 'registration/email_sent.html', vals)
    else:
        form = FirstTimeDomainRegistrationForm() # An unbound form

    vals = dict(form = form)
    return render_to_response(request, 'registration/first_domain.html', vals)

@transaction.commit_on_success
@login_required_late_eval_of_LOGIN_URL
def resend_confirmation(request):
    if request.method == 'POST': # If the form has been submitted...
        form = ResendConfirmationEmailForm(request.POST) # A form bound to the POST data
        if form.is_valid(): # All validation rules pass

            dom_req = form.retrieved_domain.registrationrequest
            try:
                send_domain_registration_email( dom_req.new_user.email, dom_req.domain.name, dom_req.activation_guid)
            except:
                vals = {'error_msg':'There was a problem with your request',
                        'error_details':sys.exc_info(),
                        'show_homepage_link': 1 }
                return render_to_response(request, 'error.html', vals)
            else:
                vals = dict(alert_message="Email sent.")
                return render_to_response(request, 'registration/email_sent.html', vals)
    else:
        form = ResendConfirmationEmailForm() # An unbound form

    vals = dict(form = form)
    return render_to_response(request, 'registration/resend_confirmation.html', vals)

@transaction.commit_on_success
def confirm_domain(request, guid=None):
    # Did we get a guid?
    vals = {}
    if guid is None:
        vals['message_title'] = 'A domain activation key was not provided.'
        vals['message_body'] = 'If you think this is an error, please contact the system administrator.'
        vals['is_error'] = True
        return render_to_response(request, 'registration/confirmation_message.html', vals)

    # Does guid exist in the system?
    reqs = RegistrationRequest.objects.filter(activation_guid=guid)
    if len(reqs) != 1:
        vals['message_title'] = 'The domain activation key "%s" provided is invalid.' % guid
        vals['message_body'] = 'If you think this is invalid, please contact the system administrator.'
        vals['is_error'] = True
        return render_to_response(request, 'registration/confirmation_message.html', vals)

    # Has guid already been confirmed?
    req = reqs[0]
    if req.domain.is_active:
        assert(req.confirm_time is not None and req.confirm_ip is not None)
        vals['message_title'] = 'The domain %s has already been activated.' % req.domain.name
        vals['message_body'] = 'No further validation is required.'
        vals['is_error'] = False
        return render_to_response(request, 'registration/confirmation_message.html', vals)

    # Set confirm time and IP; activate domain and new user who is in the
    req.confirm_time = datetime.utcnow()
    req.confirm_ip = request.META['REMOTE_ADDR']
    req.domain.is_active = True
    req.domain.save()
    req.save()

    vals['message_title'] = 'The domain %s has been successfully activated.' % req.domain.name
    vals['message_body'] = 'Thank you for taking the time to confirm your email address.'
    vals['is_error'] = False
    return render_to_response(request, 'registration/confirmation_message.html', vals)