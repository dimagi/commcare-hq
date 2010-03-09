import sys, datetime, uuid
from django import forms
from django.conf import settings
#from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.contrib.sites.models import Site
from django.core.urlresolvers import reverse
from django.core.mail import EmailMultiAlternatives, SMTPConnection
from django.core.paginator import Paginator, InvalidPage, EmptyPage
from django.db import transaction
from django.http import HttpResponseRedirect
from django.template import RequestContext

import django_tables as tables

from domain import Permissions
from domain.decorators import REDIRECT_FIELD_NAME, login_required_late_eval_of_LOGIN_URL, login_and_domain_required, domain_admin_required
from domain.forms import DomainSelectionForm, RegistrationRequestForm, ResendConfirmEmailForm, clean_password, UpdateSelfForm, UpdateSelfTable
from domain.models import Domain, Membership, RegistrationRequest
from domain.user_registration_backend.forms import AdminRegistersUserForm
from user_registration.models import RegistrationProfile

from rapidsms.webui.utils import render_to_response

# Domain not required here - we could be selecting it for the first time. See notes domain.decorators
# about why we need this custom login_required decorator
@login_required_late_eval_of_LOGIN_URL
def select( request, 
            redirect_field_name = REDIRECT_FIELD_NAME,
            domain_select_template = 'domain/select.html' ):
    
    domains_for_user = Domain.active_for_user(request.user)
    if len(domains_for_user) == 0:       
        vals = dict( error_msg = "You are not a member of any existing domains - please contact your system administrator",
                     show_homepage_link = False   )
        return render_to_response(request, 'error.html', vals)
    
    redirect_to = request.REQUEST.get(redirect_field_name, '')    
    if request.method == 'POST': # If the form has been submitted...        
        form = DomainSelectionForm(domain_list=domains_for_user,
                                   data=request.POST) # A form bound to the POST data
                     
        if form.is_valid():
            # We've just checked the submitted data against a freshly-retrieved set of domains
            # associated with the user. It's safe to set the domain in the sesssion (and we'll
            # check again on views validated with the domain-checking decorator)
            form.save(request) # Needs request because it saves domain in session
    
            #  Weak attempt to give user a good UX - make sure redirect_to isn't garbage.
            if not redirect_to or '//' in redirect_to or ' ' in redirect_to:
                redirect_to = reverse('homepage')
            return HttpResponseRedirect(redirect_to) # Redirect after POST
    else:
        # An unbound form
        form = DomainSelectionForm( domain_list=domains_for_user ) 

    vals = dict( next = redirect_to,
                 form = form )

    return render_to_response(request, domain_select_template, vals)

########################################################################################################
# 
# Raises exception on error - returns nothing
#

def _send_domain_registration_email(recipient, domain_name, guid, username):
        
    DNS_name = Site.objects.get(id = settings.SITE_ID).domain
    link = 'http://' + DNS_name + reverse('domain_registration_confirm') + guid + '/'    
    
    text_content = """
You requested a new HQ domain - \"%(domain)s\". To activate this domain, navigate to the following link
%(link)s
Thereafter, you'll be able to log on to your new domain with username "%(user)s".
"""

    html_content = """
<p>You requested a new HQ domain - \"%(domain)s\".</p> 
<p>To activate this domain, click on <a href="%(link)s">this link</a>.</p>
<p>If your email viewer won't permit you to click on that link, cut and paste the following link into your web browser:</p>
<p>%(link)s</p>
<p>Thereafter, you'll be able to log on to your new domain with username "%(user)s".</p>
"""
    params = {"domain": domain_name, "link": link, "user": username}
    text_content = text_content % params
    html_content = html_content % params
     
    # http://blog.elsdoerfer.name/2009/11/09/properly-sending-contact-form-emails-and-how-to-do-it-in-django/
    #
    # "From" header is the author
    # "Return-Path" header is the sender; the "envelope"
    #
    # Need to get this right so that SMTP servers that do "SPF" testing won't stop our email.
    # See http://en.wikipedia.org/wiki/Sender_Policy_Framework
            
    subject = 'New CommCareHQ domain "' + domain_name + '" requested - ACTIVATION REQUIRED'
    
    send_HTML_email(subject, recipient, text_content, html_content)

########################################################################################################
# 
# Raises exception on error - returns nothing
#

def send_HTML_email( subject, recipient, text_content, html_content ):

    # If you get the return_path header wrong, this may impede mail delivery. It appears that the SMTP server
    # has to recognize the return_path as being valid for the sending host. If we set it to, say, our SMTP
    # server, this will always be the case (as the server is explicitly serving the host).
    email_return_path = getattr(settings, 'DOMAIN_EMAIL_RETURN_PATH', None)
    if email_return_path is None: 
        # Get last two parts of the SMTP server as a proxy for the domain name from which this mail is sent.
        # This works for gmail, anyway.
        email_return_path =  settings.EMAIL_LOGIN
    
    email_from = getattr(settings, 'DOMAIN_EMAIL_FROM', None)
    if email_from is None:
        email_from = email_return_path
    from_header = {'From': email_from}  # From-header
    connection = SMTPConnection(username=settings.EMAIL_LOGIN,
                                   port=settings.EMAIL_SMTP_PORT,
                                   host=settings.EMAIL_SMTP_HOST,
                                   password=settings.EMAIL_PASSWORD,
                                   use_tls=True,
                                   fail_silently=False)
    
    msg = EmailMultiAlternatives(subject, text_content, email_return_path, [recipient], headers=from_header, connection=connection)
    msg.attach_alternative(html_content, "text/html")
    msg.send()

########################################################################################################

def _create_new_domain_request( request, kind, form, now ):
            
    dom_req = RegistrationRequest()
    dom_req.tos_confirmed = form.cleaned_data['tos_confirmed']
    dom_req.request_time = now
    dom_req.request_ip = request.META['REMOTE_ADDR']                
    dom_req.activation_guid = uuid.uuid1().hex         
 
    dom_is_active = False
    if kind == 'existing_user':
        dom_req.confirm_time = datetime.datetime.now()
        dom_req.confirm_ip = request.META['REMOTE_ADDR']     
        dom_is_active = True  
     
    # Req copies domain_id at initial assignment of Domain to req; does NOT get the ID from the 
    # copied Domain object just prior to Req save. Thus, we need to save the new domain before copying 
    # it over to the req, so the Domain will have a valid id 
    d = Domain(name = form.cleaned_data['domain_name'], is_active=dom_is_active)
    d.save()                                
    dom_req.domain = d                
                     
    ############# User     
    if kind == 'existing_user':   
        new_user = request.user
    else:        
        new_user = User()
        new_user.first_name = form.cleaned_data['first_name']
        new_user.last_name  = form.cleaned_data['last_name']
        new_user.username = form.cleaned_data['username']
        new_user.email = form.cleaned_data['email']
        assert(form.cleaned_data['password_1'] == form.cleaned_data['password_2'])
        new_user.set_password(form.cleaned_data['password_1'])                                                        
        new_user.is_staff = False # Can't log in to admin site
        new_user.is_active = False # Activated upon receipt of confirmation
        new_user.is_superuser = False           
        new_user.last_login = datetime.datetime(1970,1,1)
        new_user.date_joined = now
        # As above, must save to get id from db before giving to request
        new_user.save()
   
    dom_req.new_user = new_user

    # new_user must become superuser in the new domain 
    new_user.add_row_perm(d, Permissions.ADMINISTRATOR)
     
    ############# Membership
    ct = ContentType.objects.get_for_model(User)
    mem = Membership()
    mem.domain = d          
    mem.member_type = ct
    mem.member_id = new_user.id
    mem.is_active = True # Unlike domain and account, the membership is valid from the start
    mem.save()
                                                 
    # Django docs say "use is_authenticated() to see if you have a valid user"
    # request.user is an AnonymousUser if not, and that always returns False                
    if request.user.is_authenticated():
        dom_req.requesting_user = request.user
                     
    dom_req.save()        
    return dom_req

########################################################################################################

# Neither login nor domain required here - outside users, not registered on our site, can request a domain
# Manual transaction because we want to update multiple objects atomically

@transaction.commit_manually
def registration_request(request, kind=None):
    
    # Logic to decide whehter or not we're creating a new user to go with the new domain, or reusing the 
    # logged-in user's account. First we normalize kind, so it's a recognized value, and then we decide
    # what to do based in part on whether the user is logged in.    
    if not (kind=='new_user' or kind=='existing_user'):
        kind = None

    if request.user.is_authenticated():
        if kind is None:
            # Redirect to a page which lets user choose whether or not to create a new account
            vals = {}
            return render_to_response(request, 'domain/registration_reuse_account_p.html', vals)   
    else: # not authenticated
        kind = 'new_user' 
    assert(kind == 'existing_user' or kind == 'new_user')
    
    if request.method == 'POST': # If the form has been submitted...
        form = RegistrationRequestForm(kind, request.POST) # A form bound to the POST data
        if form.is_valid(): # All validation rules pass                    
            
            # Make sure we haven't violated the max reqs per day. This is defined as "same calendar date, in UTC," 
            # NOT as "trailing 24 hours"            
            now = datetime.datetime.utcnow()
            reqs_today = RegistrationRequest.objects.filter(request_time__gte = now.date()).count()
            max_req = settings.DOMAIN_MAX_REGISTRATION_REQUESTS_PER_DAY            
            if reqs_today >= max_req:
                vals = {'error_msg':'Number of domains requested today exceeds limit ('+str(max_req)+') - contact Dimagi',
                        'show_homepage_link': 1 }
                return render_to_response(request, 'error.html', vals)   
            
            try:        
                dom_req = _create_new_domain_request( request, kind, form, now )
                if kind == 'new_user': # existing_users are automatically activated; no confirmation email
                    _send_domain_registration_email( dom_req.new_user.email, dom_req.domain.name, 
                                              dom_req.activation_guid, dom_req.new_user.username )
            except:
                transaction.rollback()                
                vals = {'error_msg':'There was a problem with your request',
                        'error_details':sys.exc_info(),
                        'show_homepage_link': 1 }
                return render_to_response(request, 'error.html', vals)                   
            else:
                transaction.commit()    
    
            # Only gets here if the database-insert try block's else clause executed
            if kind == 'existing_user':
                vals = {'domain_name':dom_req.domain.name, 'username':request.user.username}
                return render_to_response(request, 'domain/registration_confirmed.html', vals)
            else: # new_user
                vals = dict(email=form.cleaned_data['email'])
                return render_to_response(request, 'domain/registration_received.html', vals)
    else:
        form = RegistrationRequestForm(kind) # An unbound form

    vals = dict(form = form, kind=kind)
    return render_to_response(request, 'domain/registration_form.html', vals)
    
########################################################################################################

# Neither login nor domain required here - outside users, not registered on our site, can request a domain
# Manual transaction because we want to update multiple objects atomically
@transaction.commit_manually
def registration_confirm(request, guid=None):
    
    # Did we get a guid?
    vals = {'show_homepage_link': 1 }    
    if guid is None:
        vals['error_msg'] = 'No domain activation key submitted - nothing to activate'                    
        return render_to_response(request, 'error.html', vals)
    
    # Does guid exist in the system?
    reqs = RegistrationRequest.objects.filter(activation_guid=guid) 
    if len(reqs) != 1:
        vals['error_msg'] = 'Submitted link is invalid - no domain with the activation key "' + guid + '" was requested'                     
        return render_to_response(request, 'error.html', vals)
    
    # Has guid already been confirmed?
    req = reqs[0]
    if req.domain.is_active:
        assert(req.confirm_time is not None and req.confirm_ip is not None)
        vals['error_msg'] = 'Domain "' +  req.domain.name + '" has already been activated - no further validation required'
        return render_to_response(request, 'error.html', vals)
    
    # Set confirm time and IP; activate domain and new user who is in the 
    try:
        req.confirm_time = datetime.datetime.now()
        req.confirm_ip = request.META['REMOTE_ADDR']     
        req.domain.is_active = True
        req.domain.save()
        req.new_user.is_active = True
        req.new_user.save() 
        req.save()
    except:
        transaction.rollback()                
        vals = {'error_msg':'There was a problem with your request',
                'error_details':sys.exc_info(),
                'show_homepage_link': 1 }
        return render_to_response(request, 'error.html', vals)
    else:
        transaction.commit()
        
    vals = {'domain_name':req.domain.name,            
            'username':req.new_user.username }
    return render_to_response(request, 'domain/registration_confirmed.html', vals)

########################################################################################################
#
# No login or domain test needed - this can be called by anonymous users
#

def registration_resend_confirm_email(request):  
    if request.method == 'POST': # If the form has been submitted...
        form = ResendConfirmEmailForm(request.POST) # A form bound to the POST data
        if form.is_valid():               
            dom_req = form.retrieved_domain.registrationrequest            
            try:
                _send_domain_registration_email( dom_req.new_user.email, dom_req.domain.name, dom_req.activation_guid, dom_req.new_user.username )
            except: 
                vals = {'error_msg':'There was a problem with your request',
                        'error_details':sys.exc_info(),
                        'show_homepage_link': 1 }
                return render_to_response(request, 'error.html', vals)
            else:        
                vals = dict(email=dom_req.new_user.email)
                return render_to_response(request, 'domain/registration_received.html', vals)
    else:
        form = ResendConfirmEmailForm()

    vals = dict(form=form)
    return render_to_response(request, 'domain/registration_resend_confirm_email.html', vals)

########################################################################################################

@login_and_domain_required
@domain_admin_required
def admin_main(request):
    return render_to_response(request, 'domain/admin_main.html',  {})

########################################################################################################
        
class UserTable(tables.Table):
    id = tables.Column(verbose_name="Id")
    username = tables.Column(verbose_name="Username")
    first_name = tables.Column(verbose_name="First name")
    last_name = tables.Column(verbose_name="Last name")
    is_active_auth = tables.Column(verbose_name="Active in system")
    is_active_member = tables.Column(verbose_name="Active in domain")
    is_domain_admin = tables.Column(verbose_name="Domain admin")
    last_login = tables.Column(verbose_name="Most recent login")
    invite_status = tables.Column(verbose_name="Invite status")    
        
########################################################################################################        
#
# Reused by all views that render a user list
#
# DUPLICATE OF patient_list_paging...this needs to be factored to a common library. Leaving it alone
# for now, though, as they're technically different applications, and we haven't put out a common 
# library yet.

def user_list_paging(request, queryset, sort_vars=None):
    # django_table checks to see if sort field is allowable - won't raise an error if the field isn't present
    # (unlike filtering of a raw queryset)
    
    order_by=request.GET.get('sort', 'username')
    user_table = UserTable(queryset, order_by)
    
    paginator = Paginator(user_table.rows, 20, orphans=2)

    # Code taken from Django dev docs explaining pagination

    # Make sure page request is an int. If not, deliver first page.
    try:
        page = int(request.GET.get('page', '1'))
    except ValueError:
        page = 1

    # If page request (9999) is out of range, deliver last page of results.
    try:
        users = paginator.page(page)
    except (EmptyPage, InvalidPage):
        users = paginator.page(paginator.num_pages)
    
    sort_index = -1
    counter = 0
    for name in user_table.columns.names():
        if order_by == name or order_by == "-%s" % name:
            sort_index = counter
            break
        counter += 1
    return render_to_response(request, 'domain/user_list.html', 
                              { 'columns': user_table.columns, 'rows':users, 'sort':order_by, 'sort_vars':sort_vars,
                                "sort_index": sort_index})
    
########################################################################################################

def _bool_to_yes_no( b ):
    return 'Yes' if b else 'No'

########################################################################################################

def _dict_for_one_user( user, domain ):
    retval = dict( id = user.id,
                   username = user.username,
                   first_name = user.first_name,
                   last_name = user.last_name,
                   is_active_auth = _bool_to_yes_no(user.is_active),          
                   last_login = user.last_login )                   
    
    is_active_member = user.domain_membership.filter(domain = domain)[0].is_active
    retval['is_active_member'] = _bool_to_yes_no(is_active_member)

    # Could use has_row_perm, which we've monkeypatched onto User, but that will take one DB call per user.
    # Going through the ORM should be faster, as we did a select_related() on the User queryset.
    ct = ContentType.objects.get_for_model(Domain)        
    is_domain_admin = user.permission_set.filter(content_type = ct, 
                                                 object_id = domain.id, 
                                                 name=Permissions.ADMINISTRATOR)
    retval['is_domain_admin'] = _bool_to_yes_no(is_domain_admin)
    
    # user is a unique get in the registrationprofile table; there can be at most
    # one invite per user, so if there is any invite at all, it's safe to just grab
    # the zero-th one
    invite_status = user.registrationprofile_set.all()
    if invite_status:
        if invite_status[0].activation_key == RegistrationProfile.ACTIVATED:
            val = 'Activated'
        else:
            val = 'Not activated'
    else:
        val = 'Admin added'
    retval['invite_status'] = val

    return retval                     
           
########################################################################################################

@login_and_domain_required
@domain_admin_required
def user_list(request):
    # Info we want to summarize for users is convoluted, and taken from several models. I don't know
    # an obvious way to get this natively from Django, and the web doesn't have an answer, so I will 
    # just walk the ORM. We might want to move to custom SQL down the line, but the total number
    # of users is likely to be small, so there's probably no performance reason to do so.
    selected_domain = request.user.selected_domain
    users = User.objects.filter(domain_membership__domain = selected_domain).select_related().all()
    table_vals = [_dict_for_one_user(u, selected_domain) for u in users]
    return user_list_paging(request, table_vals)

########################################################################################################

class AdminEditsUserForm( AdminRegistersUserForm ):
    
    def __init__(self, existing_username, editing_self, *args, **kwargs):
        super(AdminEditsUserForm, self).__init__(*args, **kwargs)
        self.existing_username = existing_username
        self.editing_self = editing_self
        self.fields['password_1'].required = False
        self.fields['password_2'].required = False
    
    def clean_username(self):
        data = self.cleaned_data['username'].strip()
        # Only throw an error if we try to CHANGE our username, and if that change will conflict with
        # another existing name
        if data != self.existing_username and User.objects.filter(username__iexact=data).count() > 0:
            raise forms.ValidationError('Username already taken; please try another')        
        return data

    def clean_password_1(self):
        # Can't get pwd_2 here yet; it hasn't been put in cleaned_data
        pwd_1 = self.cleaned_data['password_1'].strip()        
        if pwd_1:
            return clean_password(self.cleaned_data.get('password_1'))
        return pwd_1
                                  
    def clean_password_2(self):
        # Could get pwd_1 here, but no point - the overall clean
        # routine will flag the whole form if they don't match
        pwd_2 = self.cleaned_data['password_2'].strip()        
        if pwd_2:
            return clean_password(self.cleaned_data.get('password_2'))
        return pwd_2

    def _protect_user_self_edits(self, field, msg):
        data = self.cleaned_data[field]
        if self.editing_self and data == False:
            raise forms.ValidationError(msg)
        return data

    def clean_is_active(self):
        return self._protect_user_self_edits('is_active', "Can't disable your own account")
    
    def clean_is_active_member(self):
        return self._protect_user_self_edits('is_active_member', "Can't remove yourself from this domain")
    
    def clean_is_domain_admin(self):
        return self._protect_user_self_edits('is_domain_admin', "Can't remove your own admin privileges")

########################################################################################################    

@login_and_domain_required
@domain_admin_required
@transaction.commit_manually
def edit_user(request, user_id):
    
    users = User.objects.filter(domain_membership__domain = request.user.selected_domain, id = user_id).all()
    if len(users) != 1:
        detail = 'There is no user with id = ' + user_id + ' in domain "' + request.user.selected_domain.name + '"'
        vals = {'error_msg':'There was a problem with your request',
              'error_details':[detail],
              'show_homepage_link': 1 }
        return render_to_response(request, 'error.html', vals)
    user = users[0]
    membership = user.domain_membership.filter(domain = request.user.selected_domain)[0]
    # Protect user from accidentally disabling himself
    editing_self = (request.user.id == int(user_id))
    
    if request.method == 'POST': # If the form has been submitted...
        form = AdminEditsUserForm(user.username, editing_self, request.POST) # A form bound to the POST data
        if form.is_valid(): # All validation rules pass
            try:                
                user.first_name = form.cleaned_data['first_name']
                user.last_name  = form.cleaned_data['last_name']
                user.username = form.cleaned_data['username']
                user.email = form.cleaned_data['email']
                # Only put in new password if it appears to have been changed
                if form.cleaned_data['password_1']:
                    assert(form.cleaned_data['password_2'])
                    user.set_password(form.cleaned_data['password_1'])                
                user.is_active = form.cleaned_data['is_active']
                user.save()
                
                # membership            
                membership.is_active = form.cleaned_data['is_active_member']
                membership.save()
                
                # domain admin?
                if form.cleaned_data['is_domain_admin']:
                    user.add_row_perm(request.user.selected_domain, Permissions.ADMINISTRATOR)
                else:
                    user.del_row_perm(request.user.selected_domain, Permissions.ADMINISTRATOR)                                
            except:
                transaction.rollback()                
                vals = {'error_msg':'There was a problem with your request',
                        'error_details':sys.exc_info(),
                        'show_homepage_link': 1 }
                return render_to_response(request, 'error.html', vals)
            else:
                transaction.commit()
                return render_to_response(request, 'domain/user_edit_complete.html', {})
    else:
        initial = dict(first_name = user.first_name,
                       last_name = user.last_name,
                       username=user.username,
                       email=user.email,
                       # PASSWORD!
                       is_active=user.is_active,
                       is_active_member=membership.is_active,
                       # See my bugfix msg in the granular permissions app - it explains the last False param
                       is_domain_admin=user.has_row_perm(request.user.selected_domain, Permissions.ADMINISTRATOR, do_active_test=False) )
        form = AdminEditsUserForm(user.username, editing_self, initial=initial) # An unbound form
   
    vals = dict(form=form, title=' edit user in domain',form_title='Edit user - leave passwords blank if no change required')
    return render_to_response(request, 'domain/user_registration/registration_admin_does_all_form.html', vals)

########################################################################################################

########################################################################################################

@login_and_domain_required
def admin_own_account_main(request):
    return render_to_response(request, 'admin_own_account_main.html',  {})

########################################################################################################

@login_and_domain_required
def admin_own_account_update(request):
    if request.method == 'POST': # If the form has been submitted...
        form = UpdateSelfForm(request.POST) # A form bound to the POST data
        if form.is_valid(): # All validation rules pass
            user_from_db = User.objects.get(id = request.user.id)            
            table_vals = [ {'property':form.base_fields[x].label,
                            'old_val':user_from_db.__dict__[x],
                            'new_val':form.cleaned_data[x]} for x in form.cleaned_data.keys() ]

            table = UpdateSelfTable(table_vals, order_by=('Property',))              
                    
            user_from_db.__dict__.update(form.cleaned_data)
            user_from_db.save()
            return render_to_response(request, 'admin_own_account_update_done.html', dict(table=table))
    else:
        initial_vals = {}
        for x in UpdateSelfForm.base_fields.keys():            
            initial_vals[x] = request.user.__dict__[x]
        form = UpdateSelfForm(initial=initial_vals) # An unbound form - can render, but it can't validate

    vals = dict(form=form)
    return render_to_response(request, 'admin_own_account_update_form.html', vals)

########################################################################################################