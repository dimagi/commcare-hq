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
import uuid

from models import *
from django.contrib.auth.models import User 

#from forms import *
import logging
import hashlib
import settings
import traceback
import sys
import os
import string
import submitprocessor


#@login_required()
def show_submits(request, template_name="submitlogger/show_submits.html"):    
    context = {}
    slogs = SubmitLog.objects.all()
    context['submissionlog_items'] = slogs    
    return render_to_response(template_name, context, context_instance=RequestContext(request))


#@login_required()    
def single_submission(request, submit_id, template_name="submitlogger/single_submission.html"):
    context = {}        
    slog = SubmitLog.objects.all().filter(id=submit_id)
    context['submitlog_item'] = slog[0]    
    rawstring = str(slog[0].raw_header)
    rawstring = rawstring.replace(': <',': "<')
    rawstring = rawstring.replace('>,','>",')
    processed_header = eval(rawstring)
    
    attachments = Attachment.objects.all().filter(submission=slog[0])
    context ['processed_header'] = processed_header
    context['attachments'] = attachments
    return render_to_response(template_name, context, context_instance=RequestContext(request))

def raw_submit(request, template_name="submitlogger/submit.html"):
    context = {}            
    logging.debug("begin raw_submit()")
    if request.method == 'POST':
        new_submission = submitprocessor.do_raw_submission(request.META,request.raw_post_data)        
        if new_submission == '[error]':
            template_name="submitlogger/submit_failed.html"            
        else:
            context['transaction_id'] = new_submission.transaction_uuid
            context['submission'] = new_submission
            template_name="submitlogger/submit_complete.html"                                     
    return render_to_response(template_name, context, context_instance=RequestContext(request))
