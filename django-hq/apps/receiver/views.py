from django.http import HttpResponse
from django.http import HttpResponseRedirect, Http404
from django.template import RequestContext
from django.core.exceptions import *
from rapidsms.webui.utils import render_to_response
#from django.shortcuts import render_to_response, get_object_or_404
from django.shortcuts import get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import redirect_to_login
from django.utils.translation import ugettext_lazy as _
from django.db.models.query_utils import Q
from django.core.urlresolvers import reverse
from django.core.paginator import Paginator, InvalidPage, EmptyPage

from datetime import timedelta, datetime
from django.db import transaction
import uuid
import mimetypes

from receiver.models import *
from django.contrib.auth.models import User 

#from forms import *
import logging
import hashlib
#import settings
import traceback
import sys
import os
import string
import submitprocessor


@login_required()
def show_submits(request, template_name="receiver/show_submits.html"):    
    context = {}
    if ExtUser.objects.all().filter(id=request.user.id).count() == 0:
        template_name="organization/no_permission.html"
        return render_to_response(request, template_name, context)
    
    extuser = ExtUser.objects.get(id=request.user.id)
    slogs = Submission.objects.filter(domain=extuser.domain).order_by('-submit_time')
    
    paginator = Paginator(slogs, 25) # Show 25 items per page
    try:
        page = int(request.GET.get('page', '1'))
    except ValueError:
        page = 1
    
    try:
        submits_pages = paginator.page(page)
    except (EmptyPage, InvalidPage):
        submits_pages = paginator.page(paginator.num_pages)

    context['submissions'] = submits_pages    
    return render_to_response(request, template_name, context)

@login_required()    
def single_attachment(request, attachment_id):
    try:
        attachment = Attachment.objects.get(id=attachment_id)
        mtype = mimetypes.guess_type(attachment.filepath)[0]
        if mtype == None:
            response = HttpResponse(mimetype='text/plain')
        else:
            response = HttpResponse(mimetype=mtype)
        fin = open(attachment.filepath ,'r')
        txt = fin.read()
        fin.close()
        response.write(txt) 
        return response
    except:
        return ""
    
    context ['processed_header'] = processed_header
    context['attachments'] = attachments
    return render_to_response(request, template_name, context)


@login_required()    
def single_submission(request, submission_id, template_name="receiver/single_submission.html"):
    context = {}        
    slog = Submission.objects.all().filter(id=submission_id)
    context['submission_item'] = slog[0]
    rawstring = str(slog[0].raw_header)
    rawstring = rawstring.replace(': <',': "<')
    rawstring = rawstring.replace('>,','>",')
    rawstring = rawstring.replace('>}','>"}')
    processed_header = eval(rawstring)
    
    get_original = False
    for item in request.GET.items():
        if item[0] == 'get_original':
            get_original = True           
    
    if get_original:
        response = HttpResponse(mimetype='text/plain')
        fin = open(slog[0].raw_post ,'r')
        txt = fin.read()
        fin.close()
        response.write(txt) 
        return response
    
    attachments = Attachment.objects.all().filter(submission=slog[0])
    context ['processed_header'] = processed_header
    context['attachments'] = attachments
    return render_to_response(request, template_name, context)

def raw_submit(request, template_name="receiver/submit.html"):
    context = {}            
#    if request.method == 'POST':
#        new_submission = submitprocessor.do_raw_submission(request.META,request.raw_post_data)        
#        if new_submission == '[error]':
#            template_name="receiver/submit_failed.html"            
#        else:
#            context['transaction_id'] = new_submission.transaction_uuid
#            context['submission'] = new_submission
#            attachments = Attachment.objects.all().filter(submission=new_submission)            
#            context['attachments'] = attachments            
#            template_name="receiver/submit_complete.html"
            
    #for real submissions from phone, the content-type should be:
    #mimetype='text/plain' # add that to the end fo the render_to_response()                                     
    return render_to_response(request, template_name, context)

def domain_resubmit(request, domain_name, template_name="receiver/submit.html"):
    return _do_domain_submission(request, domain_name, template_name, True)

def domain_submit(request, domain_name, template_name="receiver/submit.html"):
    return _do_domain_submission(request, domain_name, template_name, False)

def _do_domain_submission(request, domain_name, template_name="receiver/submit.html", is_resubmission=False):
    context = {}
    if domain_name[-1] == '/':
        domain_name = domain_name[0:-1] #get rid of the trailing slash if it's there
    
    logging.error("begin domained raw_submit(): " + domain_name)
    currdomain = Domain.objects.filter(name=domain_name)
    if len(currdomain) != 1:
        template_name="receiver/submit_failed.html"
    if request.method == 'POST':                    
        new_submission = submitprocessor.do_raw_submission(request.META,request.raw_post_data, domain=currdomain[0], is_resubmission=is_resubmission)
        if new_submission == '[error]':
            logging.error("Domain Submit(): Submission error")
            template_name="receiver/submit_failed.html"            
        else:
            context['transaction_id'] = new_submission.transaction_uuid
            context['submission'] = new_submission
            attachments = Attachment.objects.all().filter(submission=new_submission)
            num_attachments = len(attachments)
            context['num_attachments'] = num_attachments
            template_name="receiver/submit_complete.html"
            
    #for real submissions from phone, the content-type should be:
    #mimetype='text/plain' # add that to the end fo the render_to_response()             
    #resp = render_to_response(template_name, context, context_instance=RequestContext(request))
    return render_to_response(request, template_name, context)
    

def backup(request, domain_name, template_name="receiver/backup.html"):
#return ''.join([choice('abcdefghijklmnopqrstuvwxyz0123456789!@#$%^&*(-_=+)') for i in range(50)])
    context = {}            
    logging.debug("begin backup()")
    if request.method == 'POST':
        currdomain = Domain.objects.filter(name=domain_name)
        if len(currdomain) != 1:
            new_submission = '[error]'
        else:
            new_submission = submitprocessor.do_raw_submission(request.META,request.raw_post_data, domain=currdomain[0])
                    
        if new_submission == '[error]':
            template_name="receiver/submit_failed.html"     
        else:
            #todo: get password presumably from the HTTP header            
            new_backup = Backup(submission=new_submission, password='password')
            new_backup.save()
            response = HttpResponse(mimetype='text/plain')          
                                      
            context['backup_id'] = new_backup.backup_code                        
            template_name="receiver/backup_complete.html"            
            from django.template.loader import render_to_string
            rendering = render_to_string('receiver/backup_complete.html', { 'backup_id': new_backup.backup_code })
            
            response.write(rendering)
            response['Content-length'] = len(rendering)
            return response                                         
            
    return render_to_response(request, template_name, context,mimetype='text/plain')


def restore(request, code_id, template_name="receiver/restore.html"):
    context = {}            
    logging.debug("begin restore()")
    #need to somehow validate password, presmuably via the header objects.
    restore = Backup.objects.all().filter(backup_code=code_id)
    if len(restore) != 1:
        template_name="receiver/nobackup.html"
        return render_to_response(request, template_name, context,mimetype='text/plain')
    original_submission = restore[0].submission
    attaches = Attachment.objects.all().filter(submission=original_submission)
    for attach in attaches:
        if attach.attachment_content_type == "text/xml":
            response = HttpResponse(mimetype='text/xml')
            fin = open(attach.filepath,'r')
            txt = fin.read()
            fin.close()
            response.write(txt)
            
            verify_checksum = hashlib.md5(txt).hexdigest()
            if verify_checksum == attach.checksum:                
                return response
            else:               
                continue
    
    template_name="receiver/nobackup.html"
    return render_to_response(request, template_name, context,mimetype='text/plain')
        
                           
                      
def save_post(request):
    '''Saves the body of a post in a file.  Doesn't do any processing
       of any kind.'''
    guid = str(uuid.uuid1())
    timestamp = str(datetime.now())
    filename = "%s - %s.rawpost" % (guid, timestamp)
    if request.raw_post_data:
        try:
            newfilename = os.path.join(settings.rapidsms_apps_conf['receiver']['xform_submission_path'],filename)
            logging.debug("writing to %s" % newfilename)
            fout = open(newfilename, 'w')
            fout.write(request.raw_post_data)
            fout.close()
            logging.debug("write successful")
            return HttpResponse("Thanks for submitting!  Pick up your file at %s" % newfilename)
        except Exception, e:
            logging.error(e)
            return HttpResponse("Oh no something bad happened!  %s" % e)
    return HttpResponse("Sorry, we didn't get anything there.")
    
    
    
    
    