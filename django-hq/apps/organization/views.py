# Create your views here.
from django.http import HttpResponse
from django.http import HttpResponseRedirect, Http404
from django.template import RequestContext
from django.core.exceptions import *
from django.shortcuts import render_to_response, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import redirect_to_login
from django.utils.translation import ugettext_lazy as _
from django.db.models.query_utils import Q
from django.core.urlresolvers import reverse

from datetime import timedelta
from django.db import transaction
from dbanalyzer import dbhelper

from xformmanager.models import *
from modelrelationship.models import *
from organization.models import *
from dbanalyzer.models import *
import dbanalyzer.views as chartviews

from django.contrib.auth.models import User 
from django.contrib.contenttypes.models import ContentType
import organization.utils as utils
import organization.reporter as reporter
import organization.reporter.custom as custom


#from forms import *
import logging
import hashlib
import settings
import traceback
import sys
import os
import string

import modelrelationship.traversal as traversal
import organization.reporter.inspector as repinspector

@login_required()
def dashboard(request, template_name="organization/dashboard.html"):
    context = {}
    if ExtUser.objects.all().filter(id=request.user.id).count() == 0:
        template_name="organization/no_permission.html"
        return render_to_response(template_name, context, context_instance=RequestContext(request))
        
    startdate, enddate = _get_dates(request)
    
    context['startdate'] = startdate
    context['enddate'] = enddate
    context['view_name'] = 'organization.views.dashboard'
    
    return render_to_response(template_name, context, context_instance=RequestContext(request))


@login_required()
def org_report(request, template_name="organization/org_report.html"):
    context = {}
    if ExtUser.objects.all().filter(id=request.user.id).count() == 0:
        template_name="organization/no_permission.html"
        return render_to_response(template_name, context, context_instance=RequestContext(request))
    
    # set some default parameters for start and end if they aren't passed in
    # the request
    startdate, enddate = _get_dates(request)
    
    context['startdate'] = startdate
    context['enddate'] = enddate    
    
    extuser = ExtUser.objects.all().get(id=request.user.id)        
    context['extuser'] = extuser
    context['domain'] = extuser.domain
    context['daterange_header'] = repinspector.get_daterange_header(startdate, enddate)
    context['view_name'] = 'organization.views.org_report'
    
    # get the domain from the user, the root organization from the domain,
    # and then the report from the root organization
    root_orgs = Organization.objects.filter(parent=None, domain=extuser.domain)
    # note: this pretty sneakily decides for you that you only care
    # about one root organization per domain.  should we lift this 
    # restriction?  otherwise this may hide data from you 
    root_org = root_orgs[0]
    # this call makes the meat of the report.
    context['results'] = repinspector.get_data_below(root_org, startdate, enddate, 0)
    
    return render_to_response(template_name, context, context_instance=RequestContext(request))

@login_required()
def org_email_report(request, template_name="organization/org_single_report.html"):
    context = {}
    if ExtUser.objects.all().filter(id=request.user.id).count() == 0:
        template_name="organization/no_permission.html"
        return render_to_response(template_name, context, context_instance=RequestContext(request))
    
    startdate, enddate = _get_dates(request)
    context['startdate'] = startdate
    context['enddate'] = enddate    
    
    extuser = ExtUser.objects.all().get(id=request.user.id)        
    context['extuser'] = extuser
    context['domain'] = extuser.domain
    context['daterange_header'] = repinspector.get_daterange_header(startdate, enddate)
    context['view_name'] = 'organization.views.org_email_report'
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
    #data = repinspector.get_data_below(root_org, startdate, enddate, 0)
    data = custom._get_flat_data_for_domain(extuser.domain, startdate, enddate)
    heading = "Report for period: " + startdate.strftime('%m/%d/%Y') + " - " + enddate.strftime('%m/%d/%Y')
    rendered = reporter.render_direct_email(data, startdate, enddate, 
                                          "organization/reports/email_hierarchy_report.txt", 
                                          {"heading" : heading })
    context['report_display'] = rendered
    return render_to_response(template_name, context, context_instance=RequestContext(request))

@login_required
def org_email_report_list(request, template_name="organization/org_email_report_list.html"):
    return org_report_list(request, 'organization.views.org_email_report', template_name)

@login_required
def org_sms_report_list(request, template_name="organization/org_sms_report_list.html"):
    return org_report_list(request, 'organization.views.org_sms_report', template_name)

@login_required
def org_report_list(request, single_report_url, template_name):
    context = {}
    if ExtUser.objects.all().filter(id=request.user.id).count() == 0:
        template_name="organization/no_permission.html"
        return render_to_response(template_name, context, context_instance=RequestContext(request))
    
    startdate, enddate = _get_dates(request)
    context['startdate'] = startdate
    context['enddate'] = enddate    
    
    extuser = ExtUser.objects.all().get(id=request.user.id)        
    context['extuser'] = extuser
    context['domain'] = extuser.domain
    context['daterange_header'] = repinspector.get_daterange_header(startdate, enddate)
    context['view_name'] = 'organization.views.org_sms_report_list'
    context['single_report_view'] = 'organization.views.org_sms_report'
    
    # get the domain from the user, the root organization from the domain,
    # and then the report from the root organization
    available_reports = ReportSchedule.objects.all()
    context['available_reports'] = available_reports
    
    root_orgs = Organization.objects.filter(parent=None, domain=extuser.domain)
    # note: this pretty sneakily decides for you that you only care
    # about one root organization per domain.  should we lift this 
    # restriction?  otherwise this may hide data from you 
    root_org = root_orgs[0]
    # this call makes the meat of the report.
    context['results'] = repinspector.get_data_below(root_org, startdate, enddate, 0)
    
    return render_to_response(template_name, context, context_instance=RequestContext(request))

@login_required
def org_sms_report(request, template_name="organization/org_single_report.html"):
    context = {}
    if ExtUser.objects.all().filter(id=request.user.id).count() == 0:
        template_name="organization/no_permission.html"
        return render_to_response(template_name, context, context_instance=RequestContext(request))
    
    startdate, enddate = _get_dates(request)
    context['startdate'] = startdate
    context['enddate'] = enddate    
    
    extuser = ExtUser.objects.all().get(id=request.user.id)        
    context['extuser'] = extuser
    context['domain'] = extuser.domain
    context['daterange_header'] = repinspector.get_daterange_header(startdate, enddate)
    context['view_name'] = 'organization.views.org_sms_report'
    
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
    data = custom._get_flat_data_for_domain(extuser.domain, startdate, enddate)
    heading = "Report for period: " + startdate.strftime('%m/%d/%Y') + " - " + enddate.strftime('%m/%d/%Y')
    rendered = reporter.render_direct_sms(data, startdate, enddate, 
                                          "organization/reports/sms_organization.txt", 
                                          {"heading" : heading })
    context['report_display'] = rendered
    return render_to_response(template_name, context, context_instance=RequestContext(request))

@login_required()
def register_xform(request, template_name="organization/register_xform.html"):
    return ''

@login_required()
def manage_xforms(request, template_name="oranization/manage_xforms.html"):
    return''


@login_required()
def domain_charts(request, template_name="dbanalyzer/view_graph.html"):
    context = {}
    if ExtUser.objects.all().filter(id=request.user.id).count() == 0:
        template_name="organization/no_permission.html"
        return render_to_response(template_name, context, context_instance=RequestContext(request))    

    extuser = ExtUser.objects.all().get(id=request.user.id)
    mychartgroup = utils.get_chart_group(extuser)
    if mychartgroup == None:
        return summary_trend(request)
    else:  
        return chartviews.view_group(request, mychartgroup.id)
#        context['width'] = 900
#        context['height'] = 350
#        return render_to_response(template_name, context, context_instance=RequestContext(request))    

@login_required()
def summary_trend(request, template_name="dbanalyzer/summary_trend.html"):    
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
        defs = FormDefModel.objects.all().filter(uploaded_by__domain=extuser.domain)
    
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
    return render_to_response(template_name, context, context_instance=RequestContext(request))

def _get_dates(request):
    default_delta = timedelta(days=1)
    
    enddate = datetime.datetime.now()
    startdate = datetime.datetime.now() - default_delta
    
    for item in request.GET.items():
        if item[0] == 'startdate':
            startdate_str=item[1]
            startdate = datetime.datetime.strptime(startdate_str,'%m/%d/%Y')            
        if item[0] == 'enddate':
            enddate_str=item[1]
            enddate = datetime.datetime.strptime(enddate_str,'%m/%d/%Y')                
    return (startdate, enddate)

def _get_report_id(request):
    for item in request.GET.items():
        if item[0] == 'report_id':
            return int(item[1])
    return None