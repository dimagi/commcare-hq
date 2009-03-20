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
import hashlib
import settings
import traceback
import sys


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

@transaction.commit_on_success
def raw_submit(request, template_name="submitlog_submit.html"):
    context = {}            
    logging.debug("Incoming submission")
    if request.method == 'POST':
        
        transaction = uuid.uuid1()
        new_submit = SubmitLog()
        new_submit.transaction_uuid = transaction
        new_submit.submit_ip = request.META['REMOTE_ADDR']
        new_submit.raw_header = repr(request.META)
        new_submit.checksum = hashlib.md5(request.raw_post_data).hexdigest()
        new_submit.bytes_received = int(request.META['HTTP_CONTENT_LENGTH'])
        try:
            newfilename = os.path.join(settings.XFORM_SUBMISSION_PATH,transaction + '.postdata')
            fout = open(newfilename, 'w')
            fout.write(request.raw_post_data)
            fout.close()
        except:
            logging.error("Unable to write raw post data: Exception: " + sys.exc_info()[0])
            logging.error("Unable to write raw post data: Traceback: " + sys.exc_info()[1])
            
        
        new_submit.raw_post = newfilename        
        new_submit.save()
        context['transaction_id'] = transaction    
        template_name="submitlog_submit_complete.html"             
    return render_to_response(template_name, context, context_instance=RequestContext(request))
