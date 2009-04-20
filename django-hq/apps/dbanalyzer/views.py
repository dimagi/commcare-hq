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
from xformmanager.models import *
from dbanalyzer import dbhelper
from django.utils.encoding import *
from organization.models import *

from datetime import timedelta
from django.db import transaction
import uuid

from models import *
#from forms import *
import logging
import hashlib
import settings
import traceback
import sys
import os
import string

def flot_example(request, template_name="dbanalyzer/flot_example.html"):    
    context = {}        
    context['chart_title'] = 'Sample Chart'
    context['usa_datapoint'] = 'usa'
    context['usa_label'] = "USA"
    arr = [[1988, 483994], [1989, 479060], [1990, 457648], [1991, 401949], [1992, 424705], [1993, 402375], [1994, 377867], [1995, 357382], [1996, 337946], [1997, 336185], [1998, 328611], [1999, 329421], [2000, 342172], [2001, 344932], [2002, 387303], [2003, 440813], [2004, 480451], [2005, 504638], [2006, 528692]]
    context['usa_data'] = str(arr)
    return render_to_response(template_name, context, context_instance=RequestContext(request))


def inspector(request, table_name, template_name="dbanalyzer/table_inspector.html"):
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
    
    return render_to_response(template_name, context, context_instance=RequestContext(request))
    

def view_rawgraph(request, graph_id, template_name="dbanalyzer/view_rawgraph.html"):
    context = {}    
    context['rawgraph'] = RawGraph.objects.all().get(id=graph_id)
    context['chart_title'] = context['rawgraph'].title
    context['chart_data'] = context['rawgraph'].get_flot_data()
    return render_to_response(template_name, context, context_instance=RequestContext(request))

def show_rawgraphs(request, template_name="dbanalyzer/show_rawgraphs.html"):
    context = {}    
    context['allgraphs'] = RawGraph.objects.all()
    return render_to_response(template_name, context, context_instance=RequestContext(request))

def show_multi(request, template_name="dbanalyzer/multi_graph.html"):
    context = {}    
    context['width'] = 900
    context['height'] = 350
    context['charts_to_show'] = RawGraph.objects.all()
    return render_to_response(template_name, context, context_instance=RequestContext(request))



