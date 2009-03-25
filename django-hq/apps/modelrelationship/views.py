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


from modelrelationship.models import *
from modelrelationship.forms import *
from django.contrib.auth.models import User 

#from forms import *
import logging
import hashlib
import settings
import traceback
import sys
import os
import string



def all_edgetypes(request, template_name="modelrelationship/all_edgetypes.html"):
    context = {}
    edgetypes = EdgeType.objects.all()
    context['edgetype_items'] = edgetypes    
    return render_to_response(template_name, context, context_instance=RequestContext(request))


def single_edgetype(request, edgetype_id, template_name="modelrelationship/single_edgetype.html"):
    context = {}
    edgetype = EdgeType.objects.all().get(id=edgetype_id)
    context['edgetype'] = edgetype        
    return render_to_response(template_name, context, context_instance=RequestContext(request))
    
def new_edgetype(request, form_class=EdgeTypeForm, template_name="modelrelationship/new_edgetype.html"):
    context = {}    
    new_form = form_class()
    context['form'] = new_form
    if request.method == 'POST':
        if request.POST["action"] == "create":
            new_form = form_class(request.POST)
            if new_form.is_valid():                
                newedgetype = new_form.save(commit=False)
                newedgetype.save()
                return HttpResponseRedirect(reverse('view_all_edgetypes', kwargs= {}))

    return render_to_response(template_name, context, context_instance=RequestContext(request))            
    

def new_edge(request, edgetype_id, form_class=EdgeForm, template_name="modelrelationship/new_edge.html"):
    context = {}    
    new_form = form_class(edgetype_id)
    context['form'] = new_form
    if request.method == 'POST':
        if request.POST["action"] == "create":
            new_form = form_class(edgetype_id, request.POST)
            if new_form.is_valid():                
                newedgetype = new_form.save(commit=False)
                newedgetype.save()
                return HttpResponseRedirect(reverse('view_all_edgetypes', kwargs= {}))

    return render_to_response(template_name, context, context_instance=RequestContext(request))            


def all_edges(request, template_name="modelrelationship/all_edges.html"):
    context = {}
    edges = Edge.objects.all()
    context['edge_items'] = edges    
    return render_to_response(template_name, context, context_instance=RequestContext(request))


def view_single_edge(request, edge_id, template_name="modelrelationship/single_edge.html"):
    context = {}
    edge = Edge.objects.all().get(id=edge_id)
    context['edge'] = edge        
    return render_to_response(template_name, context, context_instance=RequestContext(request))
    
