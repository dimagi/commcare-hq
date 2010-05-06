from django.http import HttpResponse, HttpResponseServerError, HttpResponseBadRequest
from django.http import HttpResponseRedirect, Http404
from django.template import RequestContext
from django.core.exceptions import *
from rapidsms.webui.utils import render_to_response
from django.shortcuts import get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import redirect_to_login
from django.utils.translation import ugettext_lazy as _
from django.db.models.query_utils import Q
from django.core.urlresolvers import reverse
from xformmanager.manager import XFormManager
# this import is just so we can get StorageUtility.XFormError
from xformmanager.storageutility import StorageUtility
from transformers.zip import get_zipfile

from uploadhandler import LegacyXFormUploadParsingHandler, LegacyXFormUploadBlobHandler

from datetime import timedelta, datetime
from django.db import transaction
import mimetypes

from receiver.models import *
from receiver.models import _XFORM_URI as XFORM_URI
from receiver.submitresponse import SubmitResponse
from django.contrib.auth.models import User

from domain.decorators import login_and_domain_required
from hq.utils import paginate


import logging
import hashlib
import traceback
import sys
import os
import string
import submitprocessor


@login_and_domain_required
def show_dupes(request, submission_id, template_name="receiver/show_dupes.html"):
    '''View duplicates of this submission.'''
    context = {}
    submit = get_object_or_404(Submission, id=submission_id)
    if submit.checksum is None or len(submit.checksum) == 0:
        # this error will go away as soon as we update all submissions 
        # to have corresponding checksums
        context['errors'] = "No checksum found. Cannot identify duplicates."
    else:
        slogs = Submission.objects.filter(checksum=submit.checksum).order_by('-submit_time')
        context['submissions'] = paginate(request, slogs)
    return render_to_response(request, template_name, context)

@login_and_domain_required
def show_submits(request, template_name="receiver/show_submits.html"):
    '''View submissions for this domain.'''
    context = {}
    slogs = Submission.objects.filter(domain=request.user.selected_domain).order_by('-submit_time')
    
    context['submissions'] = paginate(request, slogs)
    return render_to_response(request, template_name, context)

@login_and_domain_required    
def single_attachment(request, attachment_id):
    try:
        attachment = Attachment.objects.get(id=attachment_id)
        mtype = mimetypes.guess_type(attachment.filepath)[0]
        if mtype == None:
            response = HttpResponse(mimetype='text/plain')
        else:
            response = HttpResponse(mimetype=mtype)
        response.write(attachment.get_contents()) 
        return response
    except:
        return ""

@login_and_domain_required
def single_submission(request, submission_id, template_name="receiver/single_submission.html"):
    context = {}        
    slog = Submission.objects.all().filter(id=submission_id)
    context['submission'] = slog[0]
    rawstring = str(slog[0].raw_header)
    
    # In order to display the raw header information, we need to 
    # escape the python object brackets in the output 
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

def raw_submit(request):
    context = {}            
    # since this is not a real domain the following call will always
    # fail to the end-user, but at least we'll have saved the post
    # data and can have a record of the event.
    return _do_domain_submission(request, "NO_DOMAIN_SPECIFIED", is_resubmission=False)

def domain_resubmit(request, domain_name):
    return _do_domain_submission(request, domain_name, True)

def domain_submit(request, domain_name):
    return _do_domain_submission(request, domain_name, False)

def _do_domain_submission(request, domain_name, is_resubmission=False):
    if request.method != 'POST':
        return HttpResponse("You have to POST to submit data.")

    # ODK/legacy handling hack.
    # on a NON standard post (ie, not multipart/mixed), we hijack the file 
    # upload handler.
    # This is for multipart/mixed.  For text/xml, we can safely assume that 
    # it's just straight from raw_post_data.
    # and that is the case on the last case of the parsing/checksum calculation.
    if not request.META["CONTENT_TYPE"].startswith('multipart/form-data'):
        request.upload_handlers = [LegacyXFormUploadBlobHandler()]
    is_legacy_blob = False
    # get rid of the trailing slash if it's there
    if domain_name[-1] == '/':    
        domain_name = domain_name[0:-1]
        
    #ODK HACK - the ODK client appends /submission to the end of the URL.  So for testing purposes until
    #we get the header-based authentication, we need to strip out the /submission from the end.
    if len(domain_name.split('/')) > 1:
        fixdomain = domain_name.split('/')[0]
        odksuffix = domain_name.split('/')[1:]
        if odksuffix.count('submission') == 1:
            domain_name = fixdomain         

    try: 
        #Verify that the domain is valid if possible
        submit_domain = Domain.objects.get(name=domain_name)
    except Domain.DoesNotExist:
        logging.error("Submission error! %s isn't a known domain.  The submission has been saved with a null domain" % (domain_name))
        submit_domain = None
    try:        
        if request.FILES.has_key('xml_submission_file'):
            # ODK Hack. because the way in which ODK handles the uploads using 
            # multipart/form data instead of the w3c xform transport
            # we need to unwrap the submissions differently
            is_legacy_blob = False
            xform = request.FILES['xml_submission_file'].read()            
            request.FILES['xml_submission_file'].seek(0) #reset pointer back to the beginning            
            checksum = hashlib.md5(xform).hexdigest()
        elif request.FILES.has_key('raw_post_data'):        
            rawpayload = request.FILES['raw_post_data'].read()
            is_legacy_blob = True
            checksum = hashlib.md5(rawpayload).hexdigest()        
        elif len(request.raw_post_data) > 0:
            rawpayload = request.raw_post_data
            is_legacy_blob = True
            checksum = hashlib.md5(rawpayload).hexdigest()      
        else:                       
            logging.error("Submission error for domain %s, user: %s.  No data payload found." % \
                      (domain_name,str(request.user)))               
            response = SubmitResponse(status_code=500, or_status_code=5000)
            return response.to_response()     
            
    except Exception, e:
        return HttpResponseServerError("Saving submission failed!  This information probably won't help you: %s" % e)

    try: 
        new_submission = submitprocessor.new_submission(request.META, checksum, 
                                                        submit_domain, 
                                                        is_resubmission=is_resubmission)    
        if is_legacy_blob and rawpayload != None:
            submitprocessor.save_legacy_blob(new_submission, rawpayload)            
            attachments = submitprocessor.handle_legacy_blob(new_submission)
        elif is_legacy_blob == False:             
            attachments = submitprocessor.handle_multipart_form(new_submission, request.FILES)
            
        if request.user and request.user.is_authenticated():
            # set the user info if necessary
            new_submission.authenticated_to = request.user
            new_submission.save()
        
        # the receiver creates its own set of params it cares about 
        receiver_params = {}
        receiver_params['TransactionId'] = new_submission.transaction_uuid
        receiver_params['Submission'] = new_submission
        receiver_params['NumAttachments'] = len(new_submission.attachments.all())
        ways_handled = new_submission.ways_handled.all()
        # loop through the potential ways it was handled and see if any
        # of the apps want to override the response.  
        # TODO: the first response will override all the others.  These
        # need a priority and/or more engineering if we want to allow
        # multiple responses.  See reciever/__init__.py for an example
        # of this in action
        # NOTE
        for way_handled in ways_handled:
            app_name = way_handled.handled.app
            method_name = way_handled.handled.method
            try:
                module = __import__(app_name,fromlist=[''])
                if hasattr(module, method_name):
                    method = getattr(module, method_name)
                    response = method(way_handled, receiver_params)
                    if response and isinstance(response, HttpResponse):
                        return response
            except ImportError:
                # this is ok it just wasn't a valid handling method
                continue
        # either no one handled it, or they didn't want to override the 
        # response.  This falls back to the old default. 
        response = SubmitResponse(status_code=200, or_status_code=2000,
                                  submit_id=new_submission.id,
                                  **receiver_params)
        return response.to_response()
            
    except Exception, e:
        type, value, tb = sys.exc_info()
        traceback_string = "\n\nTRACEBACK: " + '\n'.join(traceback.format_tb(tb))
        logging.error("Submission error for domain %s, user: %s, header: %s" % \
                      (domain_name,str(request.user), str(request.META)), \
                      extra={'submit_exception':str(e), 'submit_traceback':traceback_string, \
                             'header':str(request.META)})
        # should we return success or failure here?  I think failure, even though
        # we did save the xml successfully.
        response = SubmitResponse(status_code=500, or_status_code=5000, 
                                  or_status="FAIL. %s" % e)
        return response.to_response()

    
@login_and_domain_required
def orphaned_data(request, template_name="receiver/show_orphans.html"):
    '''
     View data that we could not link to any known schema
    '''
    context = {}
    if request.method == "POST":
        xformmanager = XFormManager()
        count = 0
        
        def _process(submission, action):
            """
            Does the actual resubmission of a single form.
            
            return a tuple of (<success>, <message>) where:
              success = True if success, else False
              message = A helpful message about what happened
            """ 
            if action == 'delete':
                submission.delete()
                return (True, "deleted")
            elif action == 'resubmit':
                status = False
                try:
                    status = xformmanager.save_form_data(submission.xform)
                except StorageUtility.XFormError, e:
                    # if xform doesn't match schema, that's ok
                    return (False, "Expected problem: %s" % e)
                except Exception, e:
                    return (False, "Unexpected ERROR: %s" % e)
                return (status, "Completed")
            return (False, "Unknown action: %s" % action)
               
        errors = {}
        if 'select_all' in request.POST:
            submissions = Submission.objects.filter(domain=request.user.selected_domain).order_by('-submit_time')
            # TODO - optimize this into 1 db call
            for submission in submissions:
                if submission.is_orphaned():
                    status, msg = _process(submission, request.POST['action'])
                    if status: 
                        count = count + 1
                    else: 
                        errors[str(submission.id)] = msg
        else: 
            for i in request.POST.getlist('instance'):
                if 'checked_'+ i in request.POST:
                    submit_id = int(i)
                    submission = Submission.objects.get(id=submit_id)
                    status, msg = _process(submission, request.POST['action'])
                    if status:
                        count = count + 1
                    else:
                        errors[str(submission.id)] = msg
        context['status'] = "%s attempted. %s forms processed." % \
                            (request.POST['action'], count)
        context["errors"] = errors
    inner_qs = SubmissionHandlingOccurrence.objects.all().values('submission_id').query
    orphans = Submission.objects.filter(domain=request.user.selected_domain).exclude(id__in=inner_qs)
    # We could also put a check in here to not display duplicate data
    # using 'if not orphan.is_duplicate()'
    context['submissions'] = paginate(request, orphans )
    return render_to_response(request, template_name, context)

@login_and_domain_required
@transaction.commit_on_success
def delete_submission(request, submission_id=None, template='receiver/confirm_delete.html'):
    context = {}
    submission = get_object_or_404(Submission, pk=submission_id)
    if request.method == "POST":
        if request.POST["confirm_delete"]: # user has confirmed deletion.
            submission.delete()
            logging.debug("Submission %s deleted ", submission_id)
            return HttpResponseRedirect(reverse('show_submits'))
    context['object'] = submission
    context['type'] = 'Submission'
    return render_to_response(request, template, context)

@login_and_domain_required
def orphaned_data_xml(request):
    """
    Get a zip file containing all orphaned submissions
    """
    context = {}
    inner_qs = SubmissionHandlingOccurrence.objects.all().values('pk').query
    orphans = Submission.objects.exclude(id__in=inner_qs)
    attachments = Attachment.objects.filter(submission__in=orphans)
    xforms = attachments.filter(attachment_uri=XFORM_URI)
    return get_zipfile( xforms.values_list('filepath', flat=True) )

@login_and_domain_required
def annotations(request, attachment_id, allow_add=True):
    # TODO: error checking
    attach = Attachment.objects.get(id=attachment_id)
    annotes = attach.annotations.all()
    return render_to_response(request, "receiver/partials/annotations.html", {"attachment": attach, 
                                                                              "annotations": annotes, 
                                                                              "allow_add": allow_add})
@login_and_domain_required
def new_annotation(request):
    # TODO: error checking
    attach_id = request.POST["attach_id"] 
    text = request.POST["text"]
    if text and attach_id:
        attach = Attachment.objects.get(id=attach_id)
        Annotation.objects.create(attachment=attach, text=text, user=request.user)
        return HttpResponse("Success!")
    else:
        return HttpResponse("No Data!")