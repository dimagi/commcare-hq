import datetime, sys, uuid
from django import forms
from django.conf import settings
from django.contrib.sites.models import RequestSite
from django.contrib.sites.models import Site
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.core.urlresolvers import reverse
from django.db import transaction
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import redirect, render_to_response
from django.template import RequestContext
from django.utils.translation import ugettext_lazy as _

from domain import Permissions
from domain.decorators import login_and_domain_required, domain_admin_required
from domain.models import Domain, Membership, RegistrationRequest
from domain.forms import RegistrationRequestForm # Reuse to capture new user info
from domain.user_registration_backend.forms import UserEmailOnlyRegistrationRequestForm, UserRegistersSelfForm, AdminRegistersUserForm
from user_registration import signals
from user_registration.backends import get_backend
from user_registration.backends.default import DefaultBackend
from user_registration.models import RegistrationProfile

from utilities.debug_client import console_msg as cm

########################################################################################################    
    
class UserRegistersSelfBackend( DefaultBackend ):
    """
    Workflow is slightly different than that  given by the default; a domain 
    administrator can send an invite to a user, who fills out the rest of 
    his/her info.

    1. Admin inputs email of user to invite, and a dummy inactive account 
       is created. Username and password are meaningless.

    2. Email is sent to user with activation link.

    3. User clicks activation link and recieves a form that solicits the
       "real" username, first name, last name, and password. Upon successful
       receipt, the account is made active.

    Using this backend requires that

    * ``registration`` be listed in the ``INSTALLED_APPS`` setting
      (since this backend makes use of models defined in this
      application).

    * The setting ``ACCOUNT_ACTIVATION_DAYS`` be supplied, specifying
      (as an integer) the number of days from registration during
      which a user may activate their account (after that period
      expires, activation will be disallowed).

    * The creation of the templates
      ``registration/activation_email_subject.txt`` and
      ``registration/activation_email.txt``, which will be used for
      the activation email. See the notes for this backends
      ``register`` method for details regarding these templates.

    Additionally, registration can be temporarily closed by adding the
    setting ``REGISTRATION_OPEN`` and setting it to
    ``False``. Omitting this setting, or setting it to ``True``, will
    be interpreted as meaning that registration is currently open and
    permitted.

    Internally, this is accomplished via storing an activation key in
    an instance of ``registration.models.RegistrationProfile``. See
    that model and its custom manager for full documentation of its
    fields and supported operations.
    
    """    
    @transaction.commit_manually
    def register(self, request, **kwargs):
        """
        Given an email address, create a dummy user account, with a 
        nonsense username and password. They'll be filled out properly
        by the user when he/she responds to the invitation email.

        Along with the new ``User`` object, a new
        ``registration.models.RegistrationProfile`` will be created,
        tied to that ``User``, containing the activation key which
        will be used for this account. That dummy user will be given
        a membership in the domain to which the active admin (the 
        user who is sending the invitation) belongs.

        An email will be sent to the supplied email address; this
        email should contain an activation link. The email will be
        rendered using two templates. See the documentation for
        ``RegistrationProfile.send_activation_email()`` for
        information about these templates and the contexts provided to
        them.

        After the ``User`` and ``RegistrationProfile`` are created and
        the activation email is sent, the signal
        ``registration.signals.user_registered`` will be sent, with
        the new ``User`` as the keyword argument ``user`` and the
        class of this backend as the sender.

        """
        
        email = kwargs['email']
        if Site._meta.installed:
            site = Site.objects.get_current()
        else:
            site = RequestSite(request)
        
        username_max_len = User._meta.get_field('username').max_length
        username = uuid.uuid1().hex[:username_max_len]
        password = uuid.uuid1().hex # will be cut down to db field size during hashing        
    
        # Can't call create_inactive_user, because that has a commit_on_success
        # transaction wrapper. That won't work here; only the outermost function
        # (this one) can call commit or rollback. So, we'll manually carry out the
        # requisite steps: create user, create registration profile, create domain
        # membership
        
        try:
            new_user = User()
            new_user.first_name = 'unregistered'
            new_user.last_name  = 'unregistered'
            new_user.username = username
            new_user.email = email        
            new_user.set_password(password)
            new_user.is_staff = False # Can't log in to admin site
            new_user.is_active = False # Activated upon receipt of confirmation
            new_user.is_superuser = True # For now make people superusers because permissions are a pain
            new_user.last_login =  datetime.datetime(1970,1,1)
            # date_joined is used to determine expiration of the invitation key - I'd like to
            # munge it back to 1970, but can't because it makes all keys look expired.
            new_user.date_joined = datetime.datetime.utcnow()
            new_user.save()
                
            # Membership     
            ct = ContentType.objects.get_for_model(User)
            mem = Membership()
            # Domain that the current logged-on admin is in
            mem.domain = request.user.selected_domain         
            mem.member_type = ct
            mem.member_id = new_user.id
            mem.is_active = True # Unlike domain and account, the membership is valid from the start
            mem.save()        
    
            # Registration profile   
            registration_profile = RegistrationProfile.objects.create_profile(new_user)
            
            registration_profile.send_activation_email(site)
            
        except:
            transaction.rollback()                
            vals = {'error_msg':'There was a problem with your request',
                    'error_details':sys.exc_info(),
                    'show_homepage_link': 1 }
            return render_to_response('error.html', vals, context_instance = RequestContext(request))                   
        else:
            transaction.commit()  
                         
        signals.user_registered.send(sender=self.__class__,
                                     user=new_user,
                                     request=request)
        return new_user
        
        
########################################################################################################        
    
    def get_form_class(self, request):
        """
        Return the default form class used for user user_registration.
        
        """
        return UserEmailOnlyRegistrationRequestForm

########################################################################################################
    
    def post_registration_redirect(self, request, user):
        """
        Return the name of the URL to redirect to after successful
        user registration.
        
        """
        return ('registration_request_complete', (), {})
        
########################################################################################################        
    
    def post_activation_redirect(self, request, user):
        """
        Return the name of the URL to redirect to after successful
        account activation.
        
        """
        return ('registration_activation_complete', (), {'caller':'user', 'account':user.username}) 
    
########################################################################################################
    
    @transaction.commit_manually
    def activate(self, request, activation_key):
        """
        Given an an activation key, look up and activate the user
        account corresponding to that key (if possible).

        After successful activation, the signal
        ``registration.signals.user_activated`` will be sent, with the
        newly activated ``User`` as the keyword argument ``user`` and
        the class of this backend as the sender.
        
        """ 
        
        # After a user has successfully registered, the activation key is overwritten. Thus, we
        # may not be able to look it up. Downside to this design is that you can't distinguish bad
        # keys from keys that have already been used.
        try:
            profile = RegistrationProfile.objects.get(activation_key=activation_key)
        except:
            return None # Error page displayed by caller
        if profile.activation_key_expired():
            msg = "The activation key for this invitation has expired. Typical expiration is seven days from creation of the invitation."
            return render_to_response('domain/user_registration/activation_failed.html', {'msg': msg}, context_instance = RequestContext(request))    
        
        if request.method == 'POST': # If the form has been submitted...
            form = UserRegistersSelfForm(request.POST) # A form bound to the POST data
            if form.is_valid(): # All validation rules pass
                try:
                    activated = RegistrationProfile.objects.activate_user(activation_key)                               
                    if activated:                                              
                        activated.first_name = form.cleaned_data['first_name']
                        activated.last_name  = form.cleaned_data['last_name']
                        activated.username = form.cleaned_data['username']        
                        assert(form.cleaned_data['password_1'] == form.cleaned_data['password_2'])
                        activated.set_password(form.cleaned_data['password_1'])                                                                
                        activated.date_joined = datetime.datetime.utcnow() 
                        # is_active is already set by the above activate_user call
                        activated.save()
                        signals.user_activated.send(sender=self.__class__, user=activated, request=request)
                    else: 
                        # Couldn't activate - some problem with the key? Kill the transaction and return
                        # None, which prompts caller (activate_by_form) to return the error screen                        
                        transaction.rollback()
                        return None                                          
                except:
                    transaction.rollback()                
                    vals = {'error_msg':'There was a problem with your request',
                            'error_details':sys.exc_info(),
                            'show_homepage_link': 1 }
                    return render_to_response('error.html', vals, context_instance = RequestContext(request))                  
                else:
                    transaction.commit()  
                    return activated
        else:
            form = UserRegistersSelfForm() # An unbound form
    
        return render_to_response('domain/user_registration/activation_form.html', {'form': form}, context_instance = RequestContext(request))    

########################################################################################################
#
# Existing framework doesn't handle a backend that might not successfully register a user. This is a 
# modification of register to handle that case.
#

@login_and_domain_required
@domain_admin_required
def register_with_possible_errors (request, backend, success_url=None, form_class=None,
                                   disallowed_url='registration_disallowed', # URL, not form
                                   template_name='domain/user_registration/registration_form.html',
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
             template_name='domain/user_registration/activation_failed.html',
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
    cm(text_content)
    html_content = ''.join(['<p>' + x + '</p>' for x in text_content.strip().split('\n')])
    cm(html_content)

    subject = 'New CommCareHQ account'
    
    from domain.views import send_HTML_email

    send_HTML_email(subject, recipient, text_content, html_content)

########################################################################################################

@login_and_domain_required
@domain_admin_required
@transaction.commit_manually
def register_admin_does_all(request):
    if request.method == 'POST': # If the form has been submitted...
        form = AdminRegistersUserForm(request.POST) # A form bound to the POST data
        if form.is_valid(): # All validation rules pass
            try:
                new_user = User()
                new_user.first_name = form.cleaned_data['first_name']
                new_user.last_name  = form.cleaned_data['last_name']
                new_user.username = form.cleaned_data['username']
                new_user.email = form.cleaned_data['email']
                new_user.set_password(form.cleaned_data['password_1'])
                new_user.is_staff = False # Can't log in to admin site
                new_user.is_active = form.cleaned_data['is_active']
                new_user.is_superuser = False           
                new_user.last_login =  datetime.datetime(1970,1,1)
                # date_joined is used to determine expiration of the invitation key - I'd like to
                # munge it back to 1970, but can't because it makes all keys look expired.
                new_user.date_joined = datetime.datetime.utcnow()
                new_user.save()
                    
                # Membership     
                ct = ContentType.objects.get_for_model(User)
                mem = Membership()
                
                # Domain that the current logged-on admin is in 
                mem.domain = request.user.selected_domain         
                mem.member_type = ct
                mem.member_id = new_user.id
                mem.is_active = form.cleaned_data['is_active_member'] 
                mem.save()      
                
                # domain admin?
                if form.cleaned_data['is_domain_admin']:
                    new_user.add_row_perm(request.user.selected_domain, Permissions.ADMINISTRATOR)
                
                _send_user_registration_email(new_user.email, request.user.selected_domain.name, 
                                              new_user.username, form.cleaned_data['password_1'])                                 
            except:
                transaction.rollback()                
                vals = {'error_msg':'There was a problem with your request',
                        'error_details':sys.exc_info(),
                        'show_homepage_link': 1 }
                return render_to_response('error.html', vals, context_instance = RequestContext(request))                   
            else:
                transaction.commit()  
                return HttpResponseRedirect( reverse('registration_activation_complete', kwargs={'caller':'admin', 'account':new_user.username}) ) # Redirect after POST                
    else:
        form = AdminRegistersUserForm() # An unbound form
   
    return render_to_response('domain/user_registration/registration_admin_does_all_form.html', {'form': form}, context_instance = RequestContext(request)) 

########################################################################################################