from django.http import HttpResponse
from django.http import HttpResponseRedirect, Http404
from django.template import RequestContext
from django.core.exceptions import *
from django.shortcuts import render_to_response, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import redirect_to_login
from django.utils.translation import ugettext_lazy as _
from django.db.models.query_utils import Q

from datetime import timedelta
from django.db import transaction
import uuid

from models import *
from django.contrib.auth.models import User 

from forms import *
import logging



@login_required()
def show_submits(request, template_name="submitlog_show_submits.html"):    
    context = {}
    slogs = SubmitLog.objects.all()
    context['submissionlog_items'] = slogs    
    return render_to_response(template_name, context, context_instance=RequestContext(request))


@login_required()    
def single_submission(request, submit_id, template_name="submitlog_single_submission.html"):
    context = {}        
    slog = SubmitLog.objects.all().filter(id=submit_id)
    context['submitlog_item'] = slog    
    return render_to_response(template_name, context, context_instance=RequestContext(request))

def raw_submit(request, template_name="submitlog_submit.html"):
    context = {}            
    logging.debug("Incoming submission")
    if request.method == 'POST':
        logging.debug("Raw submission")
        logging.debug(request.raw_post_data)
        logging.debug("Raw post values")
        logging.debug(request.POST.values())
        logging.debug("Raw post keys")
        logging.debug(request.POST.keys())         
    return render_to_response(template_name, context, context_instance=RequestContext(request))
