import re
from datetime import timedelta
# from django.http import HttpResponse
from django.http import HttpResponseRedirect, Http404
from django.template import RequestContext
from django.core.exceptions import *
from django.views.decorators.http import require_http_methods
from django.shortcuts import get_object_or_404
from django.utils.translation import ugettext_lazy as _
from django.utils.datastructures import SortedDict
from django.db import transaction
from django.db.models.query_utils import Q
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import redirect_to_login
from django.contrib.auth.forms import AdminPasswordChangeForm
from django.contrib.auth.models import User 
from django.contrib.contenttypes.models import ContentType

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AdminPasswordChangeForm
from django.contrib.auth.models import User
from django.contrib.auth.views import login as django_login
from django.contrib.auth.views import logout as django_logout
from django.http import HttpResponseRedirect, HttpResponse

#imports fromthe django login
from django.contrib.auth import login as auth_login
from django.contrib.auth import REDIRECT_FIELD_NAME
from django.utils.http import urlquote, base36_to_int
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.cache import never_cache
from django.contrib.sites.models import Site, RequestSite
from django.contrib.auth.forms import AuthenticationForm

from corehq.apps.domain.decorators import login_and_domain_required
from corehq.util.webutils import render_to_response
import corehq.util.hqutils as utils
from corehq.apps.auditor.models import AuditEvent
from corehq.apps.auditor.decorators import log_access

from corehq.apps.xforms.models import *
# from hq.models import *
# from graphing import dbhelper
# from graphing.models import *
from corehq.apps.receiver.models import *
from corehq.apps.domain.decorators import login_and_domain_required, domain_admin_required
from corehq.apps.program.models import Program
from corehq.apps.phone.models import PhoneUserInfo


@login_and_domain_required
@log_access
def dashboard(request, template_name="hqwebapp/dashboard.html"):
    startdate, enddate = utils.get_dates(request, 7)
    
    dates = utils.get_date_range(startdate, enddate)
    dates.reverse()
    
    # we want a structure of:
    # {program: { user: {day: count}}}
    program_data_structure = {}
    program_totals = {}
    # add one to the upper bound of the metadata, to include the last day if 
    # necessary
    date_upperbound = enddate + timedelta(days=1)
    time_bound_metadatas = Metadata.objects.filter(timeend__gt=startdate)\
        .filter(timeend__lt=date_upperbound)\
        .filter(formdefmodel__domain=request.user.selected_domain)
        
    # get a list of programs --> user mappings
    # TODO: this does a lot of sql querying, for ease of readability/writability
    # if it gets slow we should optimize.
    found_meta_ids = []
    for program in Program.objects.filter(domain=request.user.selected_domain):
        program_map = SortedDict()
        program_totals_by_date = {}
        for date in dates:  program_totals_by_date[date] = 0
        program_users = User.objects.filter(program_membership__program=program)
        for program_user in program_users:
            user_date_map = {}
            for date in dates:  user_date_map[date] = 0
            user_phones = PhoneUserInfo.objects.filter(user=program_user)
            for phone in user_phones:
                # this querying will be a lot cleaner when we attach the real
                # phone object to the metadata
                phone_metas = time_bound_metadatas.filter(deviceid=phone.phone.device_id)\
                    .filter(username=phone.username)
                for meta in phone_metas:
                    user_date_map[meta.timeend.date()] += 1
                    program_totals_by_date[meta.timeend.date()] += 1
                    found_meta_ids.append(meta.id)
            program_map[program_user] = user_date_map
        program_map["Grand Total"] = program_totals_by_date    
        
        # set totals for all dates
        program_user_totals = {}
        for user, data in program_map.items():
            program_user_totals[user] = sum([value for value in data.values()])
        
        # populate data in higher level maps
        program_data_structure[program]=program_map
        program_totals[program]=program_user_totals
    
    unregistered_metas = time_bound_metadatas.exclude(id__in=found_meta_ids)
    unregistered_map = SortedDict()
    unregistered_totals_by_date = {}
    for date in dates:  unregistered_totals_by_date[date] = 0
    for meta in unregistered_metas:
        if meta.username not in unregistered_map:
            user_date_map = {}
            for date in dates:   user_date_map[date] = 0
            unregistered_map[meta.username] = user_date_map 
        unregistered_map[meta.username][meta.timeend.date()] +=1
        unregistered_totals_by_date[meta.timeend.date()] += 1
    unregistered_map["Grand Total"] = unregistered_totals_by_date
    grand_totals = {}
    for user, data in unregistered_map.items():
        grand_totals[user] = sum([value for value in data.values()])
    
    context = {"program_data": program_data_structure,
                               "program_totals": program_totals,
                               "unregistered_data": unregistered_map,
                               "unregistered_totals": grand_totals,
                               "dates": dates,
                               "startdate": startdate,
                               "enddate": enddate}
    
    
    return render_to_response(request, template_name, context)



# original
# @login_and_domain_required
# def dashboard(request, template_name="hqwebapp/dashboard.html"):
#     return render_to_response(request, template_name, 
#                               {})

@login_required()
def password_change(req):
    user_to_edit = User.objects.get(id=req.user.id)
    if req.method == 'POST': 
        password_form = AdminPasswordChangeForm(user_to_edit, req.POST)
        if password_form.is_valid():
            password_form.save()
            return HttpResponseRedirect('/')
    else:
        password_form = AdminPasswordChangeForm(user_to_edit)
    template_name="password_change.html"
    return render_to_response(req, template_name, {"form" : password_form})
    
def server_up(req):
    '''View that just returns "success", which can be hooked into server
       monitoring tools like: http://uptime.openacs.org/uptime/'''
    return HttpResponse("success")

def no_permissions(request):
    template_name="hq/no_permission.html"
    return render_to_response(request, template_name, {})


@csrf_protect
@never_cache
def login(request, template_name="login_and_password/login.html",
          redirect_field_name=REDIRECT_FIELD_NAME,
          authentication_form=AuthenticationForm):
    """Displays the login form and handles the login action."""

    redirect_to = request.REQUEST.get(redirect_field_name, '')
    request.base_template = settings.BASE_TEMPLATE
    if request.method == "POST":
        form = authentication_form(data=request.POST)
        if form.is_valid():
            # Light security check -- make sure redirect_to isn't garbage.
            if not redirect_to or ' ' in redirect_to:
                redirect_to = settings.LOGIN_REDIRECT_URL
            
            # Heavier security check -- redirects to http://example.com should 
            # not be allowed, but things like /view/?param=http://example.com 
            # should be allowed. This regex checks if there is a '//' *before* a
            # question mark.
            elif '//' in redirect_to and re.match(r'[^\?]*//', redirect_to):
                    redirect_to = settings.LOGIN_REDIRECT_URL
            
            # Okay, security checks complete. Log the user in.            
            auth_login(request, form.get_user())

            if request.session.test_cookie_worked():
                request.session.delete_test_cookie()
            
            #audit the login
            AuditEvent.objects.audit_login(request, form.get_user(), True)
            return HttpResponseRedirect(redirect_to)
        else: #failed login
            failed= form.data['username']            
            try:
                usr = User.objects.all().get(username=form.data['username'])                   
            except:
                usr = None                                
            AuditEvent.objects.audit_login(request, usr, False, username_attempt = failed)
            
        

    else:
        form = authentication_form(request)
    
    request.session.set_test_cookie()
    
    if Site._meta.installed:
        current_site = Site.objects.get_current()
    else:
        current_site = RequestSite(request)
    
    return render_to_response(request, template_name, {
        'form': form,
        redirect_field_name: redirect_to,
        'site': current_site,
        'site_name': current_site.name,
    })

def logout(request, next_page=None, template_name="hqwebapp/loggedout.html", redirect_field_name=REDIRECT_FIELD_NAME):
    "Logs out the user and displays 'You are logged out' message."
    request.base_template = settings.BASE_TEMPLATE 
    from django.contrib.auth import logout
    AuditEvent.objects.audit_logout(request, request.user)
    logout(request)    
    if next_page is None:
        redirect_to = request.REQUEST.get(redirect_field_name, '')
        if redirect_to:
            return HttpResponseRedirect(redirect_to)
        else:
            return render_to_response(request, template_name, {
                'title': _('Logged out')
            })
    else:
        # Redirect to this page until the session has been cleared.
        return HttpResponseRedirect(next_page or request.path)


#
#def login(req, template_name="login_and_password/login.html"):
#    # this view, and the one below, is overridden because 
#    # we need to set the base template to use somewhere  
#    # somewhere that the login page can access it.
#    req.base_template = settings.BASE_TEMPLATE 
#    return django_login(req, **{"template_name" : template_name})
#
#def logout(req, template_name="hqwebapp/loggedout.html"):
#    req.base_template = settings.BASE_TEMPLATE 
#    return django_logout(req, **{"template_name" : template_name})