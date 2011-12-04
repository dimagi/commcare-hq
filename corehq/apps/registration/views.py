from datetime import datetime
from django.conf import settings
from django.contrib.auth import authenticate, login
from django.db import transaction
from corehq.apps.domain.forms import RegistrationRequestForm
from corehq.apps.domain.models import RegistrationRequest
from corehq.apps.domain.views import _create_new_domain_request, _send_domain_registration_email
from corehq.apps.hqwebapp.forms import EmailAuthenticationForm
from corehq.apps.registration.forms import NewWebUserRegistrationForm
from corehq.apps.registration.utils import activate_new_user
from dimagi.utils.web import render_to_response

@transaction.commit_on_success
def register_user(request):

    if request.user.is_authenticated():
        # Redirect to a page which lets user choose whether or not to create a new account
        vals = {}
        return render_to_response(request, 'registration/currently_logged_in.html', vals)
    else:
        if request.method == 'POST': # If the form has been submitted...
            form = NewWebUserRegistrationForm(request.POST) # A form bound to the POST data
            if form.is_valid(): # All validation rules pass

                # Make sure we haven't violated the max reqs per day. This is defined as "same calendar date, in UTC,"
                # NOT as "trailing 24 hours"
                now = datetime.utcnow()
                reqs_today = RegistrationRequest.objects.filter(request_time__gte = now.date()).count()
                max_req = settings.DOMAIN_MAX_REGISTRATION_REQUESTS_PER_DAY
                if reqs_today >= max_req:
                    vals = {'error_msg':'Number of domains requested today exceeds limit ('+str(max_req)+') - contact Dimagi',
                            'show_homepage_link': 1 }
                    return render_to_response(request, 'error.html', vals)

                activate_new_user(form)
                new_user = authenticate(username=form.cleaned_data['email'], password=form.cleaned_data['password'])
                login(request, new_user)
                # Only gets here if the database-insert try block's else clause executed
                vals = dict(email=form.cleaned_data['email'])
                print "success"
                #return render_to_response(request, 'domain/registration_received.html', vals)
        else:
            form = NewWebUserRegistrationForm() # An unbound form

        vals = dict(form = form)
        #return django_login(req, template_name=template_name, authentication_form=EmailAuthenticationForm)
        return render_to_response(request, 'registration/new_user.html', vals)