from django.http import HttpResponse, HttpResponseRedirect, Http404, HttpRequest, QueryDict
from django.shortcuts import get_object_or_404
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
from reports.custom.shared import Mother


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


@login_and_domain_required
def report(request, format):
    context = {'clinic' : _get_clinic(request) }
    context['hq_mode'] = (context['clinic']['name'] == 'HQ')

    showclinic = request.GET['clinic'] if request.GET.has_key('clinic') else context['clinic']['id']
    context['showclinic'] = showclinic
    
    # hi risk view?
    hi_risk_only = request.path.replace(".%s" % format, '').endswith('/risk')
    context['page'] = 'risk' if hi_risk_only else 'all' 
        
    if request.GET.has_key('meta_username'):
        showclinic = None
        if hi_risk_only:
            context['title'] = "Hi Risk Cases Entered by %s" % request.GET['meta_username']
        else:
            context['title'] = "Cases Entered by %s" % request.GET['meta_username']
        
        if request.GET.has_key('follow') and request.GET['follow'] == 'yes':
            context['title'] += ", Followed Up"

    # filter by CHW name
    filter_chw = request.GET['meta_username'] if request.GET.has_key('meta_username') else None
    chws = [filter_chw] if filter_chw else chws_for(showclinic)
    rows = registrations().filter(meta_username__in=chws).order_by('sampledata_mother_name')

    if hi_risk_only: rows = rows.filter(sampledata_hi_risk='yes')

    # filter by a specific risk indicator (for links from the HQ view "High Risk" page)
    if request.GET.has_key('filter'):
        filt = "%s.%s" % (REGISTRATION_TABLE, HI_RISK_INDICATORS[request.GET['filter']]['where'])
        rows = rows.extra(where=[filt])
        context['title'] = '%s <span style="color: #646462">Cases in</span> %s' % \
                            (HI_RISK_INDICATORS[request.GET['filter'].strip()]['long'], Clinic.objects.get(id=request.GET['clinic']).name)

    # for search by mother name
    search = request.GET['search'] if request.GET.has_key('search') else ''
    search = search.strip()    
    if search != '':
        rows = rows.filter(sampledata_mother_name__icontains=search)
        
            
    visits = clinic_visits(clinic_id=showclinic, chw_name=filter_chw)
    
    # finally, pack it up and ship to the template/CSV
    # Django's retarded template language forces this bollocks
    # So might as well use it to stitch in visits & attachments
    atts = attachments_for(REGISTRATION_TABLE)    
    items = []
    for i in rows:
        at = atts[i.id] if atts.has_key(i.id) else None
        try:
            visit = visits["%s-%s-%s" % (i.sampledata_mother_name, i.meta_username, i.sampledata_case_id)]
        except KeyError:
            visit = False
        items.append({ "row" : i, "attach" : at, "visit": visit })
        
    # filter only mothers who visited the clinic
    if request.GET.has_key('visited'):
        items = filter(lambda i:i['visit'], items)

        
    context['items'] = items   
    context['search_term'] = search
    # for record_visit to return to
    context['return_to'] = "%s?%s" % (request.path, request.META['QUERY_STRING'])
    
    # CSV export
    if format == 'csv':
        csv = 'Mother Name,Address,Hi Risk?,Visited Clinic?,Follow up?,Most Recent Follow Up\n'
        for i in items:
            row = i['row']
            visited = i['visit'].created_at.strftime('%B %d, %Y') if i['visit'] else "No"
            msg = i['attach'].most_recent_annotation() if i['attach'] is not None else ""
            if msg is None:
                follow = "no"
                msg = ""
            else:
                follow = "yes"
                msg = str(msg).replace('"', '""').replace("\n", " ")

            csv += '"%s","%s","%s","%s","%s","%s"\n' % (row.sampledata_mother_name, row.sampledata_address, row.sampledata_hi_risk, visited, follow, msg)

        response = HttpResponse(mimetype='text/csv')
        response['Content-Disposition'] = 'attachment; filename=pregnant_mothers.csv'
        response.write(csv)
        return response

    # or plain HTML 
    else:
        return render_to_response(request, "report.html", context)
    
@login_and_domain_required
def record_visit(request):
    ClinicVisit(
        mother_name=request.POST['mother_name'], 
        chw_name=request.POST['chw_name'], 
        chw_case_id=request.POST['chw_case_id'],
        clinic=Clinic.objects.get(id=request.POST['clinic_id'])
    ).save()
    
    return HttpResponseRedirect(request.POST['return_to'])
    
    
@login_and_domain_required    
def mother_details(request):
    chw, case_id = request.GET['case_id'].split('|')
    mother_name = request.GET['mother_name']
    
    mother_id = registrations().get(sampledata_mother_name=mother_name, sampledata_case_id=case_id, meta_username=chw).id
    
    context = {'clinic' : _get_clinic(request), 'page': "single"}
    context['hq_mode'] = (context['clinic']['name'] == 'HQ')
        
    case = get_object_or_404(Case, name="Grameen Safe Pregnancies")

    data = case.get_data_map_for_case(request.GET["case_id"])
    mom = Mother(case, case_id, data)

    if mom.mother_name != mother_name:
        return HttpResponse("ID %s points to more than one person (mom.mother_name: %s, mother_name: %s)" % (request.GET["case_id"], mom.mother_name, mother_name))

    attrs = [name for name in dir(mom) if not name.startswith("_")]
    attrs.remove("data_map")
    display_attrs = [attr.replace("_", " ") for attr in attrs]
    
    context['mother'] = mom
    context['attrs'] = zip(attrs, display_attrs)
    
    # get attachment ID for SMS Sending UI
    atts = attachments_for(REGISTRATION_TABLE)
    context['attach_id'] = atts[mother_id].id
    
    reasons = []
    if (mom.mother_age >= 35):              reasons.append("35 or older") 
    if (mom.mother_age <= 18):              reasons.append("18 or younger")
    if (mom.mother_height == 'under_150'):  reasons.append("Mother height under 150cm")
    if (mom.previous_csection == 'yes'):    reasons.append("Previous C-section")
    if (mom.over_5_years == 'yes'):         reasons.append("Over 5 years since last pregnancy")
    if (mom.previous_bleeding == 'yes'):    reasons.append("Previous bleeding")
    if (mom.previous_terminations >= 3):    reasons.append("%s previous terminations" % mom.previous_terminations)
    if (mom.previous_pregnancies >= 5):     reasons.append("%s previous pregnancies" % mom.previous_pregnancies)
    if (mom.heart_problems == 'yes'):       reasons.append("Heart problems")
    if (mom.diabetes == 'yes'):             reasons.append("Diabetes")
    if (mom.hip_problems == 'yes'):         reasons.append("Hip problems")
    if (mom.previous_newborn_death == 'yes'):           reasons.append("Previous newborn death")
    if (mom.card_results_hb_test == 'below_normal'):    reasons.append("Low hb test")
    if (mom.card_results_blood_group == 'onegative'):   reasons.append("O-negative blood group")
    if (mom.card_results_blood_group == 'anegative'):   reasons.append("A-negative blood group")
    if (mom.card_results_blood_group == 'abnegative'):  reasons.append("AB-negative blood group")
    if (mom.card_results_blood_group == 'bnegative'):   reasons.append("B-negative blood group")
    if (mom.card_results_hepb_result == 'positive'):    reasons.append("Positive for hepb")
    if (mom.card_results_syphilis_result == 'positive'):    reasons.append("Positive for syphilis")
    
    context['risk_factors'] = reasons
    
    return render_to_response(request, "mother_details.html", context)


# Chart Methods
@login_and_domain_required
def chart(request, template_name="chart.html"):    
    context = {'page' : "chart" , 'clinic' : _get_clinic(request)}
    context['hq_mode'] = (context['clinic']['name'] == 'HQ')

    graph = RawGraph() #.objects.all().get(id=29)
    graph.set_fields({
          "series_labels": "Count", 
          "data_source": "", 
          "y_axis_label": "Number of Submissions", 
          "x_type": "MM/DD/YYYY", 
          "additional_options": {"yaxis" : {"tickDecimals": 0}}, 
          "time_bound": 1, 
          "default_interval": 365, 
          "interval_ranges": "7|30|90|365", 
          "x_axis_label": "Date", 
          "table_name": "xformmanager_metadata", 
          "display_type": "compare-cumulative", 
    })
    
    startdate, enddate = utils.get_dates(request, graph.default_interval)    
    graph.db_query = clinic_chart_sql(startdate, enddate, context['clinic']['id']) #startdate, enddate, context['clinic']['id'])    
    
    context['chart_data'] = graph.get_flot_data()
    context['thegraph'] = graph    

    rootgroup = utils.get_chart_group(request.user)    
    graphtree = _get_graphgroup_children(rootgroup)    
    context['graphtree'] = graphtree
    context['width'] = graph.width
    context['height'] = graph.height
    context['datatable'] = graph.convert_data_to_table(context['chart_data'])
        
    context['chw_reg_cols'], context['chw_reg_rows'] = _get_chw_registrations_table(context['clinic']['id'])
    context['total_hi_risk'] = 0 ; context['total_registrations'] = 0 ; context['total_follow_up'] = 0
    
    for item in context['chw_reg_rows']:
        context['total_registrations']  += item['reg']    or 0
        context['total_hi_risk']        += item['risk']   or 0
        context['total_follow_up']      += item['follow'] or 0

    context['total_visits'] = len(clinic_visits(context['clinic']['id'])) #sum([i for i in clinic_visits(context['clinic']['id']).values()])

    return render_to_response(request, template_name, context)
    
    
# per clinic UI
@login_and_domain_required
def hq_chart(request, template_name="hq_chart.html"):
    context = { 'page': "hq_chart", 'clinic' : _get_clinic(request) }
    context['hq_mode'] = (context['clinic']['name'] == 'HQ')

    graph = RawGraph() #.objects.all().get(id=27)
    
    graph.set_fields({
      "series_labels": "Count", 
      "data_source": "", 
      "y_axis_label": "Number of Submissions", 
      "x_type": "MM/DD/YYYY", 
      "additional_options": {"yaxis": {"tickDecimals": 0}}, 
      "time_bound": 1, 
      "default_interval": 365, 
      "interval_ranges": "7|30|90|365", 
      "x_axis_label": "Date", 
      "table_name": "xformmanager_metadata", 
      "display_type": "compare-cumulative", 
    })

    startdate, enddate = utils.get_dates(request, graph.default_interval)
    graph.db_query = hq_chart_sql(startdate, enddate)

    context['chart_data'] = graph.get_flot_data()
    context['thegraph'] = graph
    
    rootgroup = utils.get_chart_group(request.user)    
    graphtree = _get_graphgroup_children(rootgroup)    
    context['graphtree'] = graphtree
    context['width'] = graph.width
    context['height'] = graph.height

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
            visits = len(clinic_visits(c.id))
        context['clinics'].append({'name': c, 'reg': d['reg'][c.id], 'hi_risk': d['hi_risk'][c.id], 'follow': d['follow'][c.id], 'visits': visits})    
  
    # get per CHW table for show/hide
    context['chw_reg_cols'], context['chw_reg_rows'] = _get_chw_registrations_table()
    
    return render_to_response(request, template_name, context)


@login_and_domain_required
def hq_risk(request, template_name="hq_risk.html"):
    context = { 'page' : "hq_risk", 'clinic' : _get_clinic(request) }
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
    context['visits']  = len(clinic_visits(clinic_id=showclinic.id))
        
    graph = RawGraph() #.objects.all().get(id=28)

    graph.set_fields({
      "default_interval": 365, 
      "series_labels": "Total | <150cm | C-Sect | Pr.Death | Pr.Bleed | Heart | Diabetes | Hip | Syph | Hep B | Long Time | Lo.Hmglb | Age<19 | Age>34 | Pr.Term | Pr.Preg | Rare Bld", 
      "data_source": "", 
      "y_axis_label": "Number of Registrations", 
      "x_type": "string", 
      "additional_options": {"legend": { "show": True }}, 
      "time_bound": 0, 
      "x_axis_label": "High Risk Indicators", 
      "width": 800, 
      "interval_ranges": "", 
      "table_name": "schema_intel_grameen_safe_motherhood_registration_v0_3", 
      "display_type": "histogram-multifield-sorted",
      "height": 450, 
    })

    graph.db_query = hq_risk_sql(showclinic.id)

    context['chart_data'] = graph.get_flot_data()
    context['thegraph'] = graph
    
    rootgroup = utils.get_chart_group(request.user)    
    graphtree = _get_graphgroup_children(rootgroup)    
    context['graphtree'] = graphtree
    context['width'] = graph.width
    context['height'] = graph.height
    data = graph.convert_data_to_table(context['chart_data'])
    
    # populate indicators table
    indicators = graph.get_dataset_as_dict()[0]    
    context['indicators'] = []
    for ind in HI_RISK_INDICATORS:
        context['indicators'].append([ind, indicators[ind], HI_RISK_INDICATORS[ind]['long']])
        
    context['indicators'].sort(key=lambda x:x[1], reverse=True) # sort by value, making sure Total is first item in the process
    
    # get per CHW table for show/hide
    context['chw_reg_cols'], context['chw_reg_rows'] = _get_chw_registrations_table()
        
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

        d['visits'] = len(clinic_visits(chw_name=d['name']))
        rows.append(d)
    
    # add clinic visits
    cols.append('# of Clinic Visits')

    return cols, rows


def _get_clinic(request):
    try:
        clinic_id = UserClinic.objects.get(username=request.user.username).clinic_id
        clinic_name = Clinic.objects.get(id=clinic_id).name
        return {'id' : clinic_id, 'name' : clinic_name}
    except:
        return {}
