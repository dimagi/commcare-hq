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
from djflot import dbhelper
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

def flot_example(request, template_name="djflot/flot_example.html"):    
    context = {}        
    context['chart_title'] = 'Sample Chart'
    context['usa_datapoint'] = 'usa'
    context['usa_label'] = "USA"
    arr = [[1988, 483994], [1989, 479060], [1990, 457648], [1991, 401949], [1992, 424705], [1993, 402375], [1994, 377867], [1995, 357382], [1996, 337946], [1997, 336185], [1998, 328611], [1999, 329421], [2000, 342172], [2001, 344932], [2002, 387303], [2003, 440813], [2004, 480451], [2005, 504638], [2006, 528692]]
    context['usa_data'] = str(arr)
    return render_to_response(template_name, context, context_instance=RequestContext(request))


@login_required()
def summary_trend(request, template_name="djflot/summary_trend.html"):    
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
        defs = FormDefData.objects.all().filter(uploaded_by__domain=extuser.domain)
    
        for fdef in defs:            
            d = dbhelper.DbHelper(fdef.element.table_name, fdef.form_display_name)            
            context['dataset'][fdef.form_display_name.__str__()] = d.get_counts_dataset(None,None)                    
    
    else:
        fdef = FormDefData.objects.all().filter(id=formdef_id)
        context['chart_title'] = fdef[0].form_display_name
        d = dbhelper.DbHelper(fdef[0].element.table_name,fdef[0].form_display_name)        
        context['dataset'] = d.get_integer_series_dataset()
    
    context ['maxdate'] = 0;
    context ['mindate'] = 0;
    return render_to_response(template_name, context, context_instance=RequestContext(request))

