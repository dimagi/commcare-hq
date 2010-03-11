import logging
import hashlib
import settings
import traceback
import sys
import os
import uuid
import string
from datetime import timedelta

from django.http import HttpResponse
from django.http import HttpResponseRedirect, Http404
from django.template import RequestContext
from django.core.exceptions import *
from django.views.decorators.http import require_http_methods
from django.shortcuts import get_object_or_404
from django.utils.translation import ugettext_lazy as _
from django.db import transaction
from django.db.models.query_utils import Q
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import redirect_to_login
from django.contrib.auth.forms import AdminPasswordChangeForm
from django.contrib.auth.models import User 
from django.contrib.contenttypes.models import ContentType

from rapidsms.webui.utils import render_to_response, paginated

from xformmanager.models import *
from hq.models import *
from graphing import dbhelper
from graphing.models import *
from receiver.models import *
from domain.decorators import login_and_domain_required, domain_admin_required
    
import hq.utils as utils
import hq.reporter as reporter
import hq.reporter.custom as custom
import hq.reporter.metastats as metastats

import hq.reporter.inspector as repinspector
import hq.reporter.metadata as metadata

from reporters.utils import *
from reporters.views import message, check_reporter_form, update_reporter
from reporters.models import Reporter, PersistantBackend, PersistantConnection


logger_set = False

@login_and_domain_required
def dashboard(request, template_name="hq/dashboard.html"):
    context = {}
    startdate, enddate = utils.get_dates(request, 7)
    context['startdate'] = startdate
    context['enddate'] = enddate
    context['view_name'] = 'hq.views.dashboard'
    return render_to_response(request, template_name, context)


@login_and_domain_required
def reporter_stats(request, template_name="hq/reporter_stats.html"):
    context = {}       
    # the decorator and middleware ensure this will be set.
    statdict = metastats.get_stats_for_domain(request.user.selected_domain)        
    context['reporterstats'] = statdict    
    
    return render_to_response(request, template_name, context)


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

@require_http_methods(["GET", "POST"])
@login_and_domain_required
def add_reporter(req):
    # NOTE/TODO:
    # this is largely a copy paste job from rapidsms/apps/reporters/views.py
    # method of the same name, and really doesn't belong here at all. 
    
    def get(req):
        # pre-populate the "connections" field
        # with a connection object to convert into a
        # reporter, if provided in the query string
        connections = []
        if "connection" in req.GET:
            connections.append(
                get_object_or_404(
                    PersistantConnection,
                    pk=req.GET["connection"]))
        
        return render_to_response(req,
            "hq/reporter.html", {
                
                # display paginated reporters in the left panel
                "reporters": paginated(req, Reporter.objects.all()),
                
                # pre-populate connections
                "connections": connections,
                
                # list all groups + backends in the edit form
                "all_groups": ReporterGroup.objects.flatten(),
                "all_backends": PersistantBackend.objects.all() })

    @transaction.commit_manually
    def post(req):
        # check the form for errors
        reporter_errors = check_reporter_form(req)
        profile_errors = check_profile_form(req)
        
        # if any fields were missing, abort.
        missing = reporter_errors["missing"] + profile_errors["missing"]
        exists = reporter_errors["exists"] + profile_errors["exists"]
        
        if missing:
            transaction.rollback()
            return message(req,
                "Missing Field(s): %s" % comma(missing),
                link="/reporters/add")
        # if chw_id exists, abort.
        if exists:
            transaction.rollback()
            return message(req,
                "Field(s) already exist: %s" % comma(exists),
                link="/reporters/add")
        
        try:
            # create the reporter object from the form
            rep = insert_via_querydict(Reporter, req.POST)
            rep.save()
            
            # add relevent connections
            update_reporter(req, rep)
            # create reporter profile
            update_reporterprofile(req, rep, req.POST.get("chw_id", ""), \
                                   req.POST.get("chw_username", ""))
            # save the changes to the db
            transaction.commit()
            
            # full-page notification
            return message(req,
                "Reporter %d added" % (rep.pk),
                link="/reporters")
        
        except Exception, err:
            transaction.rollback()
            raise
    
    # invoke the correct function...
    # this should be abstracted away
    if   req.method == "GET":  return get(req)
    elif req.method == "POST": return post(req)


    
@require_http_methods(["GET", "POST"])  
def edit_reporter(req, pk):
    rep = get_object_or_404(Reporter, pk=pk)
    rep_profile = get_object_or_404(ReporterProfile, reporter=rep)
    rep.chw_id = rep_profile.chw_id
    rep.chw_username = rep_profile.chw_username
    
    def get(req):
        return render_to_response(req,
            "hq/reporter.html", {
                
                # display paginated reporters in the left panel
                "reporters": paginated(req, Reporter.objects.all()),
                
                # list all groups + backends in the edit form
                "all_groups": ReporterGroup.objects.flatten(),
                "all_backends": PersistantBackend.objects.all(),
                
                # split objects linked to the editing reporter into
                # their own vars, to avoid coding in the template
                "connections": rep.connections.all(),
                "groups":      rep.groups.all(),
                "reporter":    rep })
    
    @transaction.commit_manually
    def post(req):
        
        # if DELETE was clicked... delete
        # the object, then and redirect
        if req.POST.get("delete", ""):
            pk = rep.pk
            rep_profile.delete()
            rep.delete()
            
            transaction.commit()
            return message(req,
                "Reporter %d deleted" % (pk),
                link="/reporters")
                
        else:
            # check the form for errors (just
            # missing fields, for the time being)
            reporter_errors = check_reporter_form(req)
            profile_errors = check_profile_form(req)
            
            # if any fields were missing, abort. this is
            # the only server-side check we're doing, for
            # now, since we're not using django forms here
            missing = reporter_errors["missing"] + profile_errors["missing"]
            if missing:
                transaction.rollback()
                return message(req,
                    "Missing Field(s): %s" %
                        ", ".join(missing),
                    link="/reporters/%s" % (rep.pk))
            
            try:
                # automagically update the fields of the
                # reporter object, from the form
                update_via_querydict(rep, req.POST).save()
                # add relevent connections
                update_reporter(req, rep)
                # update reporter profile
                update_reporterprofile(req, rep, req.POST.get("chw_id", ""), \
                                       req.POST.get("chw_username", ""))
                
                # no exceptions, so no problems
                # commit everything to the db
                transaction.commit()
                
                # full-page notification
                return message(req,
                    "Reporter %d updated" % (rep.pk),
                    link="/reporters")
            
            except Exception, err:
                transaction.rollback()
                raise
        
    # invoke the correct function...
    # this should be abstracted away
    if   req.method == "GET":  return get(req)
    elif req.method == "POST": return post(req)

def update_reporterprofile(req, rep, chw_id, chw_username):
    try:
        profile = ReporterProfile.objects.get(reporter=rep)
    except ReporterProfile.DoesNotExist:
        profile = ReporterProfile(reporter=rep, approved=True, active=True, \
                                  guid = str(uuid.uuid1()).replace('-',''))
        # reporters created through the webui automatically have the same
        # domain and organization as the creator
        profile.domain = request.user.selected_domain
         
    profile.chw_id = chw_id
    profile.chw_username = chw_username
    profile.save()

def check_profile_form(req):
    errors = {}
    errors['missing'] = []
    # we currently do not enforce the requirement for chw_id or chw_username
    #if req.POST.get("chw_id", "") == "":
    #    errors['missing'] = errors['missing'] + ["chw_id"]
    #if req.POST.get("chw_username", "") == "":
    #    errors['missing'] = errors['missing'] + ["chw_username"]
    
    errors['exists'] = []
    chw_id = req.POST.get("chw_id", "")
    if chw_id:
        # if chw_id is set, it must be unique for a given domain
        rps = ReporterProfile.objects.filter(chw_id=req.POST.get("chw_id", ""), domain=req.user.selected_domain)
        if rps: errors['exists'] = ["chw_id"]
    return errors


def no_permissions(request):
    template_name="hq/no_permission.html"
    return render_to_response(request, template_name, {})

def comma(string_or_list):
    """ TODO - this could probably go in some sort of global util file """
    if isinstance(string_or_list, basestring):
        string = string_or_list
        return string
    else:
        list = string_or_list
        return ", ".join(list)

