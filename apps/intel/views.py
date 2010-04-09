from django.http import HttpResponse, HttpResponseRedirect, Http404, HttpRequest, QueryDict
from django.template import RequestContext
from django.core.exceptions import *

from rapidsms.webui.utils import render_to_response

from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import redirect_to_login
from django.contrib.auth.models import User

from django.utils.translation import ugettext_lazy as _
from django.db.models.query_utils import Q
from xformmanager.models import *
from graphing import dbhelper
from django.utils.encoding import *
from hq.models import *

import hq.utils as utils
from domain.decorators import login_and_domain_required

from transformers.csv import UnicodeWriter
from StringIO import StringIO

from datetime import timedelta
from django.db import transaction
import uuid

from graphing.models import *
import logging
import hashlib
import settings
import traceback
import sys
import os
import string

import reports.util as util
from reports.custom.all.shared import get_data_by_chw, get_case_info
from reports.models import Case, SqlReport

# import intel.queries as queries
from intel.models import *

# A note about user authorization
# The current system enforces user auth, and provides a plain path for where users go, depending on their role
# but it is lenient regarding what users *can* see if they enter the right URLs
# So, users can access the HQ UI if they want to
# or see HQ/Doctor views, if they know the URLs
# 
# The idea is to make it easier to maintain/debug
# and allow users who wish to, to get to know the system further than their restricted paths

@login_and_domain_required
def homepage(request):
    context = { 'clinic' : _get_clinic(request) }
    context['hq_mode'] = (context['clinic']['name'] == 'HQ')
        
    return render_to_response(request, "home.html", context)
    

######## Report Methods
@login_and_domain_required
def all_mothers_report(request, format):
    '''View all mothers - default'''

    title = ""
    
    if request.GET.has_key('meta_username'): 
        title = "Cases Entered by %s" % request.GET['meta_username']
        
    if request.GET.has_key('follow') and request.GET['follow'] == 'yes':
        title += ", Followed Up"
        
    return _custom_report(request, 3, "chw_submission_details", "all", title, format)

@login_and_domain_required
def hi_risk_report(request, format):
    '''View only hi risk'''
    title = ""
    if request.GET.has_key('meta_username'): 
        title = "Cases Entered by %s" % request.GET['meta_username']
    
    return _custom_report(request, 3, "hi_risk_pregnancies", "risk", title, format)

@login_and_domain_required
def mother_details(request):
    '''view details for a mother'''
    return _custom_report(request, 3, "_mother_summary", "single")
    


def _custom_report(request, domain_id, report_name, page, title=None, format=None):
    context = { 'clinic' : _get_clinic(request) }

    context['page'] = page
    context["report_name"] = report_name
    context['title'] = title

    context['hq_mode'] = (context['clinic']['name'] == 'HQ')
    params = { 'clinic' : context['clinic']['id'] } if context['clinic']['name'] != 'HQ' else {}
        
    report_method = util.get_report_method(request.user.selected_domain, report_name)
    if not report_method:
        return render_to_response(request, 
                                  "report_not_found.html",
                                  context)
 
    context["report_display"] = report_method.__doc__
        
    if format == 'csv':
        cols, rows = report_method(request, params, False)
        
        csv = 'Mother Name,Address,Hi Risk?,Follow up?,Most Recent Follow Up\n'
        for r in rows:
            msg = r['attachment'].most_recent_annotation()
            if msg is None: 
                msg = ""
            else:
                msg = str(msg).replace('"', '""')
                
            csv += '"%s","%s","%s","%s","%s"\n' % (r['Mother Name'], r['Address'], r['Hi Risk?'], r['Follow up?'], msg)

        response = HttpResponse(mimetype='text/csv')
        response['Content-Disposition'] = 'attachment; filename=pregnant_mothers.csv'
        response.write(csv)
        return response

    context["report_body"] = report_method(request, params)

    
    if 'search' not in request.GET.keys(): 
        context['search_term'] = ''
    else:
        context['search_term'] = request.GET['search']
        
        
    return render_to_response(request, "report.html", context)


# Chart Methods
@login_and_domain_required
def chart(request, template_name="chart.html"):    
    context = { 'clinic' : _get_clinic(request) }
    graph = RawGraph.objects.all().get(id=29) #20)

    context['hq_mode'] = (context['clinic']['name'] == 'HQ')
    graph.clinic_id = context['clinic']['id']
    
    graph.domain = request.user.selected_domain.name
    startdate, enddate = utils.get_dates(request, graph.default_interval)
    graph.startdate = startdate.strftime("%Y-%m-%d")
    graph.enddate = (enddate + timedelta(days=1)).strftime("%Y-%m-%d")

    # print startdate.strftime("%Y-%m-%d"), (enddate + timedelta(days=1)).strftime("%Y-%m-%d")

    context['chart_title'] = graph.title
    
    context['chart_data'] = graph.get_flot_data()
    context['thegraph'] = graph
    
    context['page'] = "chart"

    rootgroup = utils.get_chart_group(request.user)    
    graphtree = _get_graphgroup_children(rootgroup)    
    context['graphtree'] = graphtree
    context['view_name'] = 'chart.html'
    context['width'] = graph.width
    context['height'] = graph.height
    context['empty_dict'] = {}
    context['datatable'] = graph.convert_data_to_table(context['chart_data'])
        
    context['chw_reg_cols'], context['chw_reg_rows'] = _get_chw_registrations_table(context['clinic']['id'])
    context['total_hi_risk'] = 0 ; context['total_registrations'] = 0 ; context['total_follow_up'] = 0
    
    for item in context['chw_reg_rows']:
        context['total_registrations']  += item['reg'] or 0
        context['total_hi_risk']        += item['risk'] or 0
        context['total_follow_up']      += item['follow'] or 0

    
    for item in request.GET.items():
        if item[0] == 'bare':
            template_name = 'graphing/view_graph_bare.html'
        elif item[0] == 'data':
            template_name='graphing/view_graph_data.html'
        elif item[0] == 'csv':             
            return _get_chart_csv(graph)
            
    return render_to_response(request, template_name, context)
    
    
# per clinic UI
@login_and_domain_required
def hq_chart(request, template_name="hq_chart.html"):
    context = { 'clinic' : _get_clinic(request) }
    context['hq_mode'] = (context['clinic']['name'] == 'HQ')

    graph = RawGraph.objects.all().get(id=27)

    graph.domain = request.user.selected_domain.name
    startdate, enddate = utils.get_dates(request, graph.default_interval)
    graph.startdate = startdate.strftime("%Y-%m-%d")
    graph.enddate = (enddate + timedelta(days=1)).strftime("%Y-%m-%d")

    context['chart_title'] = graph.title
    
    context['chart_data'] = graph.get_flot_data()
    context['thegraph'] = graph
    
    context['page'] = "hq_chart"

    rootgroup = utils.get_chart_group(request.user)    
    graphtree = _get_graphgroup_children(rootgroup)    
    context['graphtree'] = graphtree
    # context['view_name'] = 'chart.html'
    context['width'] = graph.width
    context['height'] = graph.height
    context['empty_dict'] = {}
    context['datatable'] = graph.convert_data_to_table(context['chart_data'])
    
    clinics = Clinic.objects.exclude(name='HQ')
    
    d = {
        'reg' : registrations_by('clinic_id'),
        'hi_risk' : hi_risk_by('clinic_id'),
        'follow' : followup_by('clinic_id')
        }

    context['clinics'] = []    
    for c in clinics:
        for k in d.keys():
            if not d[k].has_key(c.id):
                d[k][c.id] = 0
        context['clinics'].append({'name': c, 'reg': d['reg'][c.id], 'hi_risk': d['hi_risk'][c.id], 'follow': d['follow'][c.id]})    
  
    # get per CHW table for show/hide
    context['chw_reg_cols'], context['chw_reg_rows'] = _get_chw_registrations_table()
    
    for item in request.GET.items():
        if item[0] == 'bare':
            template_name = 'graphing/view_graph_bare.html'
        elif item[0] == 'data':
            template_name='graphing/view_graph_data.html'
        elif item[0] == 'csv':             
            return _get_chart_csv(graph)
            
    return render_to_response(request, template_name, context)


@login_and_domain_required
def hq_risk(request, template_name="hq_risk.html"):
    context = { 'clinic' : _get_clinic(request) }
    context['hq_mode'] = (context['clinic']['name'] == 'HQ')
    
    clinics = Clinic.objects.exclude(name='HQ')
    
    # find current clinic. if id is missing/wrong, use the first clinic
    try:
        showclinic = clinics.get(id=int(request.GET['clinic']))
    except:
        showclinic = clinics[0]
        
    context['clinics'] = clinics
    context['showclinic'] = showclinic
    
    reg = registrations_by('clinic_id')
    hi  = hi_risk_by('clinic_id')
    fol = followup_by('clinic_id')

    context['regs']    = reg[showclinic.id] if reg.has_key(showclinic.id) else 0
    context['hi_risk'] = hi[showclinic.id]  if hi.has_key(showclinic.id)  else 0
    context['follow']  = fol[showclinic.id] if fol.has_key(showclinic.id) else 0
        
        
    graph = RawGraph.objects.all().get(id=28)

    graph.domain = request.user.selected_domain.name

    graph.clinic_id = showclinic.id
    
    startdate, enddate = utils.get_dates(request, graph.default_interval)
    graph.startdate = startdate.strftime("%Y-%m-%d")
    graph.enddate = (enddate + timedelta(days=1)).strftime("%Y-%m-%d")

    graph.width = 800
    
    context['chart_title'] = graph.title
    
    context['chart_data'] = graph.get_flot_data()
    context['thegraph'] = graph
    
    context['page'] = "hq_risk"

    rootgroup = utils.get_chart_group(request.user)    
    graphtree = _get_graphgroup_children(rootgroup)    
    context['graphtree'] = graphtree
    # context['view_name'] = 'chart.html'
    context['width'] = graph.width
    context['height'] = graph.height
    context['empty_dict'] = {}
    data = graph.convert_data_to_table(context['chart_data'])
    
    # context['datatable'] = graph.convert_data_to_table(context['chart_data'])
        
    context['indicators'] = zip(data[0], data[1])
    
    # get per CHW table for show/hide
    context['chw_reg_cols'], context['chw_reg_rows'] = _get_chw_registrations_table()
        
    for item in request.GET.items():
        if item[0] == 'bare':
            template_name = 'graphing/view_graph_bare.html'
        elif item[0] == 'data':
            template_name='graphing/view_graph_data.html'
        elif item[0] == 'csv':             
            return _get_chart_csv(graph)

    return render_to_response(request, template_name, context)
    

def _get_graphgroup_children(graph_group):
    ret = {}
    children = GraphGroup.objects.all().filter(parent_group=graph_group)
    for child in children:
        ret[child] = _get_graphgroup_children(child)
    return ret
    

# get per CHW table for show/hide
def _get_chw_registrations_table(clinic_id = None):    
    report = SqlReport.objects.get(id=1).get_data()
    
    # work directly with the data - we know the format we're expecting. if it changes, so will this code
    cols = report[0][:4] # 'Healthcare Worker', '# of Patients', '# of High Risk', '# of Follow Up'
    rows = []
    for row in report[1]:   # (u'CHAVEZ', 11L, 6L, None, u'Madhabpur', '1')
        d = dict(zip(('name', 'reg', 'risk', 'follow', 'clinic', 'clinic_id'), row))
        if clinic_id is not None and clinic_id != d['clinic_id']: continue

        # convert None to 0
        for i in d:
            if d[i] is None: d[i] = 0
        rows.append(d)
    
    return cols, rows


def _get_clinic(request):
    try:
        clinic_id = UserClinic.objects.get(username=request.user.username).clinic_id
        clinic_name = Clinic.objects.get(id=clinic_id).name
        return {'id' : clinic_id, 'name' : clinic_name}
    except:
        return {}
