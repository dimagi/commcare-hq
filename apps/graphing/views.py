# Create your views here.
from django.http import HttpResponse
from django.http import HttpResponseRedirect, Http404
from django.template import RequestContext
from django.core.exceptions import *

from rapidsms.webui.utils import render_to_response

from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import redirect_to_login
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

from models import *
import logging
import hashlib
import settings
import traceback
import sys
import os
import string


@login_and_domain_required
def domain_charts(request):
    context = {}
    mychartgroup = utils.get_chart_group(request.user)
    if mychartgroup == None:
        return summary_trend(request)
    else:  
        return view_group(request, mychartgroup.id)

@login_and_domain_required
def summary_trend(request, template_name="graphing/summary_trend.html"):
    """This is just a really really basic trend of total counts for a given set 
       of forms under this domain/organization"""    
    context = {}        
    formname = ''
    formdef_id = -1
    
    for item in request.GET.items():
        if item[0] == 'formdef_id':
            formdef_id=item[1]    
    if formdef_id == -1:
        context['chart_title'] = 'All Data'
        context['dataset'] = {}        
        defs = FormDefModel.objects.all().filter(domain=request.user.selected_domain)
    
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


def inspector(request, table_name, template_name="graphing/table_inspector.html"):
    context = {}
    context['table_name'] = table_name
    
    str_column = None
    str_column_value = None
    datetime_column = None
    data_column = None
    display_mode = None    
    
    for item in request.GET.items():
        if item[0] == 'str_column':
            str_column = item[1]                    
        if item[0] == 'str_column_value':
            str_column_value = item[1] 
        if item[0] == 'datetime_column':
            datetime_column = item[1]   
        if item[0] == 'data_column':
            data_column = item[1]        
        if item[0] == 'display_mode':
            display_mode = item[1]    
            
    context['str_column'] = str_column
    context['str_column_value'] = str_column_value
    context['datetime_column'] = datetime_column
    context['data_column'] = data_column
    context['display_mode'] = display_mode    
    
    return render_to_response(request, template_name, context)




@login_and_domain_required
def view_graph(request, graph_id, template_name="graphing/view_graph.html"):
    context = {}    
    graph = RawGraph.objects.all().get(id=graph_id)
    
    #get the root group
    # inject some stuff into the rawgraph.  we can also do more
    # here but for now we'll just work with the domain and set 
    # some dates.  these can be templated down to the sql
    graph.domain = request.user.selected_domain.name
    startdate, enddate = utils.get_dates(request, graph.default_interval)
    graph.startdate = startdate.strftime("%Y-%m-%d")
    graph.enddate = (enddate + timedelta(days=1)).strftime("%Y-%m-%d")
    
    context['chart_title'] = graph.title
    context['chart_data'] = graph.get_flot_data()
    context['thegraph'] = graph
    
    rootgroup = utils.get_chart_group(request.user)    
    graphtree = get_graphgroup_children(rootgroup)    
    context['graphtree'] = graphtree
    context['view_name'] = 'graphing.views.view_graph'
    context['width'] = graph.width
    context['height'] = graph.height
    context['empty_dict'] = {}
    context['datatable'] = graph.convert_data_to_table(context['chart_data'])
    for item in request.GET.items():
        if item[0] == 'bare':
            template_name = 'graphing/view_graph_bare.html'
        elif item[0] == 'data':
            template_name='graphing/view_graph_data.html'
        elif item[0] == 'csv':             
            return _get_chart_csv(graph)
    return render_to_response(request, template_name, context)

@login_and_domain_required
def show_allgraphs(request, template_name="graphing/show_allgraphs.html"):
    context = {}    
    context['allgraphs'] = RawGraph.objects.all()    
    return render_to_response(request, template_name, context)

@login_and_domain_required
def show_multi(request, template_name="graphing/multi_graph.html"):
    context = {}    
    context['width'] = 900
    context['height'] = 350
    context['charts_to_show'] = RawGraph.objects.all()
    return render_to_response(request, template_name, context)


@login_and_domain_required
def view_groups(request, template_name="graphing/view_groups.html"):
    context = {}    
    context['groups'] = GraphGroup.objects.all()
    return render_to_response(request, template_name, context)

    context = {}


def get_graphgroup_children(graph_group):
    ret = {}
    children = GraphGroup.objects.all().filter(parent_group=graph_group)
    for child in children:
        ret[child] = get_graphgroup_children(child)
    return ret
    
@login_and_domain_required
def view_group(request, group_id, template_name="graphing/view_group.html"):
    context = {}
    group = GraphGroup.objects.all().get(id=group_id)
    context['group'] = group  
    context['group_charts'] = []
    context['width'] = 900
    context['height'] = 350
    
    for thegraph in group.graphs.all():
        if hasattr(thegraph,'rawgraph'):
            context['group_charts'].append(thegraph.rawgraph)
        else:
            context['group_charts'].append(thegraph)    
    
    context['child_groups'] = GraphGroup.objects.all().filter(parent_group=group)
    
    rootgroup = utils.get_chart_group(request.user)    
    graphtree = get_graphgroup_children(rootgroup)
    context['graphtree'] = graphtree
    
    return render_to_response(request, template_name, context)

def _get_chart_csv(chart):
    datatable = chart.get_data_as_table()
    output = StringIO()
    w = UnicodeWriter(output)
    for row in datatable:
        w.writerow(row)
    output.seek(0)
    response = HttpResponse(output.read(),
                        mimetype='application/ms-excel')
    response["content-disposition"] = 'attachment; filename="%s-%s.csv"' % ( chart.title, str(datetime.datetime.now().date()))
    return response
    
    

