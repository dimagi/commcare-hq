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
from domain.decorators import login_and_domain_required
from webutils import render_to_response

import datahq.shared_code.hqutils as utils

from xformmanager.models import *
# from hq.models import *
# from graphing import dbhelper
# from graphing.models import *
from receiver.models import *
from domain.decorators import login_and_domain_required, domain_admin_required
from program.models import Program
from phone.models import PhoneUserInfo


@login_and_domain_required
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
    
    return render_to_response(request, template_name, 
                              {"program_data": program_data_structure,
                               "program_totals": program_totals,
                               "unregistered_data": unregistered_map,
                               "unregistered_totals": grand_totals,
                               "dates": dates,
                               "startdate": startdate,
                               "enddate": enddate})



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

def login(req, template_name="login_and_password/login.html"):
    # this view, and the one below, is overridden because 
    # we need to set the base template to use somewhere  
    # somewhere that the login page can access it.
    req.base_template = settings.BASE_TEMPLATE 
    return django_login(req, **{"template_name" : template_name})

def logout(req, template_name="hqwebapp/loggedout.html"):
    req.base_template = settings.BASE_TEMPLATE 
    return django_logout(req, **{"template_name" : template_name})