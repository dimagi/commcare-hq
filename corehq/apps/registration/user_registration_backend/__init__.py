import datetime
from django.conf import settings
from django.contrib.sites.models import Site
from django.contrib.auth.models import User
from django.core.urlresolvers import reverse
from django.http import HttpResponse
from django.shortcuts import redirect, render_to_response
from django.template import RequestContext

from corehq.apps.domain.decorators import login_and_domain_required, domain_admin_required
from dimagi.utils.couch.database import get_db
from dimagi.utils.decorators.profile import profile
from django_user_registration.backends import get_backend

########################################################################################################
from corehq.apps.users.models import CouchUser, WebUser
from dimagi.utils.django.email import send_HTML_email

########################################################################################################
#
# Existing framework doesn't handle a backend that might not successfully register a user. This is a 
# modification of register to handle that case.
#

@login_and_domain_required
@domain_admin_required
def register_with_possible_errors (request, backend, success_url=None, form_class=None,
                                   disallowed_url='registration_disallowed', # URL, not form
                                   template_name='registration/domain_request.html',
                                   extra_context=None):
  
    backend = get_backend(backend)
    if not backend.registration_allowed(request):
        return redirect(disallowed_url)
    if form_class is None:
        form_class = backend.get_form_class(request)

    if request.method == 'POST':
        form = form_class(data=request.POST, files=request.FILES)
        if form.is_valid():
            new_user = backend.register(request, **form.cleaned_data)
            if isinstance(new_user, User):
                if success_url is None:
                    to, args, kwargs = backend.post_registration_redirect(request, new_user)
                    return redirect(to, *args, **kwargs)
                else:
                    return redirect(success_url)
            elif isinstance(new_user, HttpResponse):
                # HttpResponse object was put out by the form - just return it
                return new_user   
                
    else:
        form = form_class()
    
    if extra_context is None:
        extra_context = {}
    context = RequestContext(request)
    for key, value in extra_context.items():
        context[key] = callable(value) and value() or value

    return render_to_response(template_name,
                              { 'form': form },
                              context_instance=context)
    
#######################################################################################################
#
# Existing framework won't accomodate an activation phase that takes in more data, from a form, at
# the activation URL. This is a modification of activate to handle this case.
#

def activate_by_form (request, backend,
             template_name='registration/backend/activation_failed.html',
             success_url=None, extra_context=None, **kwargs):

    backend = get_backend(backend)
    account = backend.activate(request, **kwargs)

    if isinstance(account, User):
        if success_url is None:
            to, args, kwargs = backend.post_activation_redirect(request, account)
            return redirect(to, *args, **kwargs)
        else:
            return redirect(success_url)
        
    elif isinstance(account, HttpResponse):
        # HttpResponse object was put out by the form - just return it
        return account
    
    else: # error case - should've returned None from call to backend.activate
        assert(account is None)
        if extra_context is None:
            extra_context = {}
        context = RequestContext(request)
        for key, value in extra_context.items():
            context[key] = callable(value) and value() or value
    
        return render_to_response(template_name,
                                  kwargs,
                                  context_instance=context)

########################################################################################################
# 
# Raises exception on error - returns nothing
#

def _send_user_registration_email(recipient, domain_name, username, password):
        
    DNS_name = Site.objects.get(id = settings.SITE_ID).domain
    link = 'http://' + DNS_name + reverse('homepage')
    
    text_content = """
An administrator of CommCareHQ domain "%s" has set up an account for you.
Your username is "%s", and your password is "%s".
To login, navigate to the following link:
%s
"""
    text_content = text_content % (domain_name, username, password, link)
    html_content = ''.join(['<p>' + x + '</p>' for x in text_content.strip().split('\n')])

    subject = 'New CommCareHQ account'
    
    send_HTML_email(subject, recipient, html_content,
                    text_content=text_content)

########################################################################################################

def register_user(domain, first_name, last_name, email, password, is_domain_admin, send_email):
    new_user = WebUser.create(domain, username=email, password=password, email=email, is_admin=is_domain_admin)

    new_user.first_name = first_name
    new_user.last_name  = last_name
    new_user.username = email
    new_user.email = email
    new_user.is_staff = False # Can't log in to admin site
    new_user.is_active = True
    new_user.is_superuser = False
    new_user.last_login =  datetime.datetime(1970,1,1)
    # date_joined is used to determine expiration of the invitation key - I'd like to
    # munge it back to 1970, but can't because it makes all keys look expired.
    new_user.date_joined = datetime.datetime.utcnow()
    new_user.save()
        
    if send_email:
        _send_user_registration_email(new_user.email, domain, new_user.username, password)

    return new_user

########################################################################################################
