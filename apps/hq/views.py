# Create your views here.
from django.http import HttpResponse
from django.http import HttpResponseRedirect, Http404
from django.template import RequestContext
from django.core.exceptions import *

from rapidsms.webui.utils import render_to_response
from django.shortcuts import get_object_or_404

from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import redirect_to_login
from django.utils.translation import ugettext_lazy as _
from django.db.models.query_utils import Q
from django.core.urlresolvers import reverse
from django.contrib.auth.forms import AdminPasswordChangeForm

from datetime import timedelta
from django.db import transaction
from graphing import dbhelper

from xformmanager.models import *
from hq.models import *
from graphing.models import *
from receiver.models import *
import graphing.views as chartviews

from django.contrib.auth.models import User 
from django.contrib.contenttypes.models import ContentType
import hq.utils as utils
import hq.reporter as reporter
import hq.reporter.custom as custom
import hq.reporter.metastats as metastats


import logging
import hashlib
import settings
import traceback
import sys
import os
import string

import hq.reporter.inspector as repinspector
import hq.reporter.metadata as metadata


logger_set = False

@login_required()
def dashboard(request, template_name="hq/dashboard.html"):
    # this is uber hacky - set the log level to debug on the dashboard
    
    context = {}
    if ExtUser.objects.all().filter(id=request.user.id).count() == 0:
        template_name="hq/no_permission.html"
        return render_to_response(request, template_name, context)
        
    startdate, enddate = utils.get_dates(request, 7)
    
    context['startdate'] = startdate
    context['enddate'] = enddate
    context['view_name'] = 'hq.views.dashboard'
    return render_to_response(request, template_name, context)

@login_required()
def org_report(request, template_name="hq/org_single_report.html"):
   # return org_email_report(request)
   
    context = {}
    
    try: 
        extuser = ExtUser.objects.all().get(id=request.user.id)
    except MyModel.DoesNotExist:
        template_name="hq/no_permission.html"
        return render_to_response(template_name, context, context_instance=RequestContext(request))
        
    if extuser.organization == None:
        orgs = Organization.objects.filter(domain=extuser.domain)
    else:
        orgs = [extuser.organization]
    
    # set some default parameters for start and end if they aren't passed in
    # the request
    startdate, enddate = utils.get_dates(request)
    context['startdate'] = startdate
    context['enddate'] = enddate        
            
    context['extuser'] = extuser
    context['domain'] = extuser.domain
    context['daterange_header'] = repinspector.get_daterange_header(startdate, enddate)
    context['view_name'] = 'hq.views.org_report'
    
    context['organization_data'] = {}    
    
    do_sms = False
    for item in request.GET.items():
        if item[0] == 'sms':
            do_sms = True    
    
    rendered = ''
    if startdate == enddate:
        heading = "Report for %s" % startdate.strftime('%m/%d/%Y') 
    else: 
        heading = "Report for period: " + startdate.strftime('%m/%d/%Y') + " - " + enddate.strftime('%m/%d/%Y')
    
    if do_sms:
        rendering_template = "hq/reports/sms_organization.txt"
        renderfunc = reporter.render_direct_sms
    else:
        rendering_template = "hq/reports/email_hierarchy_report.txt"
        renderfunc = reporter.render_direct_email 
        
        
    for org in orgs:
        context['organization_data'][org] = metadata.get_org_reportdata(org, startdate, enddate)
        data = metadata.get_org_reportdata(org, startdate, enddate)
        rendered =  rendered + "<br>" + renderfunc(data, startdate, enddate,     
                                          rendering_template, 
                                          {"heading" : heading })
    context['report_display'] = rendered
    context['report_title'] = "Submissions per day for all CHWs"
        
    ## this call makes the meat of the report.
    #context['results'] = repinspector.get_data_below(root_org, startdate, enddate, 0)
    
    #return render_to_response(template_name, context, context_instance=RequestContext(request))
    return render_to_response(request, template_name, context)


@login_required()
def reporter_stats(request, template_name="hq/reporter_stats.html"):
    context = {}       
    extuser = ExtUser.objects.all().get(id=request.user.id)        
    context['extuser'] = extuser
    context['domain'] = extuser.domain
    
    statdict = metastats.get_stats_for_domain(context['domain'])        
    context['reporterstats'] = statdict    
    
    return render_to_response(request, template_name, context)

@login_required()
def delinquent_report(request, template_name="hq/reports/sms_delinquent_report.txt"):
    context = {}       
    extuser = ExtUser.objects.all().get(id=request.user.id)        
    context['extuser'] = extuser
    context['domain'] = extuser.domain
    context['delinquent_reporterprofiles'] = []    
    statdict = metastats.get_stats_for_domain(context['domain'])    
    for reporter_profile, result in statdict.items():
        lastseen = result['Time since last submission (days)']
        if lastseen > 3:
            context['delinquent_reporterprofiles'].append(reporter_profile)    
    return render_to_response(request, template_name, context)


@login_required()
def org_email_report(request, template_name="hq/org_single_report.html"):
    context = {}
    if ExtUser.objects.all().filter(id=request.user.id).count() == 0:
        template_name="hq/no_permission.html"
        return render_to_response(request, template_name, context)
    
    startdate, enddate = utils.get_dates(request)
    context['startdate'] = startdate
    context['enddate'] = enddate    
    extuser = ExtUser.objects.all().get(id=request.user.id)        
    context['extuser'] = extuser
    context['domain'] = extuser.domain
    context['daterange_header'] = repinspector.get_daterange_header(startdate, enddate)
    context['view_name'] = 'hq.views.org_email_report'
    #context['view_args'] = {"id" : id}
    
    # get the domain from the user, the root organization from the domain,
    # and then the report from the root organization
    #reporter.
    root_orgs = Organization.objects.filter(parent=None, domain=extuser.domain)
    # note: this pretty sneakily decides for you that you only care
    # about one root organization per domain.  should we lift this 
    # restriction?  otherwise this may hide data from you 
    root_org = root_orgs[0]
    
    # this call makes the meat of the report.
    data = repinspector.get_data_below(Organization.objects.all()[0], startdate, enddate, 0)
    
    # we add one to the enddate because the db query is not inclusive.
    #data = custom._get_flat_data_for_domain(extuser.domain, startdate, enddate + timedelta(days=1))
    if startdate == enddate:
        heading = "Report for %s" % startdate.strftime('%m/%d/%Y') 
    else: 
        heading = "Report for period: " + startdate.strftime('%m/%d/%Y') + " - " + enddate.strftime('%m/%d/%Y')
    rendered = reporter.render_direct_email(data, startdate, enddate, 
                                          "hq/reports/email_hierarchy_report.txt", 
                                          {"heading" : heading })
    context['report_display'] = rendered
    context['report_title'] = "Submissions per day for all CHWs"
    return render_to_response(request, template_name, context)


@login_required
def org_sms_report(request, template_name="hq/org_single_report.html"):
    context = {}
    if ExtUser.objects.all().filter(id=request.user.id).count() == 0:
        template_name="hq/no_permission.html"
        return render_to_response(request, template_name, context)
    
    startdate, enddate = utils.get_dates(request)
    context['startdate'] = startdate
    context['enddate'] = enddate    
    
    extuser = ExtUser.objects.all().get(id=request.user.id)        
    context['extuser'] = extuser
    context['domain'] = extuser.domain
    context['daterange_header'] = repinspector.get_daterange_header(startdate, enddate)
    context['view_name'] = 'hq.views.org_sms_report'
    
    # commented out because these reports aren't actually different reports
    # report = ReportSchedule.objects.get(id=id)
    # context["report"] = report
    # get the domain from the user, the root organization from the domain,
    # and then the report from the root organization
    #reporter.
    root_orgs = Organization.objects.filter(parent=None, domain=extuser.domain)
    # note: this pretty sneakily decides for you that you only care
    # about one root organization per domain.  should we lift this 
    # restriction?  otherwise this may hide data from you 
    root_org = root_orgs[0]
    
    # this call makes the meat of the report.
    #data = repinspector.get_data_below(root_org, startdate, enddate, 0)
    #data = custom._get_flat_data_for_domain(extuser.domain, startdate, enddate + timedelta(days=1))
    data = custom._get_flat_data_for_domain(extuser.domain, startdate, enddate + timedelta(days=1))
    heading = "Report for period: " + startdate.strftime('%m/%d/%Y') + " - " + enddate.strftime('%m/%d/%Y')
    rendered = reporter.render_direct_sms(data, startdate, enddate, 
                                          "hq/reports/sms_organization.txt", 
                                          {"heading" : heading })
    context['report_display'] = rendered
    return render_to_response(request, template_name, context)


@login_required()
def domain_charts(request):
    context = {}
    if ExtUser.objects.all().filter(id=request.user.id).count() == 0:
        template_name="hq/no_permission.html"
        return render_to_response(request, template_name, context)    

    extuser = ExtUser.objects.all().get(id=request.user.id)
    mychartgroup = utils.get_chart_group(extuser)
    if mychartgroup == None:
        return summary_trend(request)
    else:  
        return chartviews.view_group(request, mychartgroup.id)

@login_required()
def summary_trend(request, template_name="graphing/summary_trend.html"):
    """This is just a really really basic trend of total counts for a given set of forms under this domain/organization"""    
    context = {}        
    
    formname = ''
    formdef_id = -1
    extuser = ExtUser.objects.all().get(id=request.user.id)
    
    for item in request.GET.items():
        if item[0] == 'formdef_id':
            formdef_id=item[1]    
    if formdef_id == -1:
        context['chart_title'] = 'All Data'
        context['dataset'] = {}        
        defs = FormDefModel.objects.all().filter(domain=extuser.domain)
    
        for fdef in defs:            
            d = dbhelper.DbHelper(fdef.element.table_name, fdef.form_display_name)            
            context['dataset'][fdef.form_display_name.__str__()] = d.get_counts_dataset(None,None)                    
    
    else:
        fdef = FormDefModel.objects.all().filter(id=formdef_id)
        context['chart_title'] = fdef[0].form_display_name
        d = dbhelper.DbHelper(fdef[0].element.table_name,fdef[0].form_display_name)        
        context['dataset'] = d.get_integer_series_dataset()
    
    context ['maxdate'] = 0;
    context ['mindate'] = 0;
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