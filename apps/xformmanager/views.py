import settings, os, sys
import tempfile
import logging
import traceback
import hashlib
import csv
from StringIO import StringIO
import util as xutils
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.http import HttpResponse, HttpResponseRedirect
from django.template import RequestContext
from django.db import transaction, connection
from django.core.urlresolvers import reverse
from django.contrib.auth.decorators import login_required
from rapidsms.webui.utils import render_to_response
from xformmanager.forms import RegisterXForm, SubmitDataForm
from xformmanager.models import FormDefModel
from xformmanager.xformdef import FormDef
from xformmanager.manager import *
from receiver.submitprocessor import do_old_submission

from hq.models import *
from hq.utils import paginate
from hq.decorators import extuser_required

from transformers.csv import UnicodeWriter
from transformers.zip import get_zipfile

from receiver.models import Attachment
from django.db.models import signals

@extuser_required()
@transaction.commit_manually
def remove_xform(request, form_id=None, template='confirm_delete.html'):
    context = {}
    extuser = request.extuser
    
    form = get_object_or_404(FormDefModel, pk=form_id)
    
    if request.method == "POST":
        if request.POST["confirm_delete"]: # The user has already confirmed the deletion.
            xformmanager = XFormManager()
            xformmanager.remove_schema(form_id)
            logging.debug("Schema %s deleted ", form_id)
            #self.message_user(request, _('The %(name)s "%(obj)s" was deleted successfully.') % {'name': force_unicode(opts.verbose_name), 'obj': force_unicode(obj_display)})                    
            return HttpResponseRedirect("../register")
    context['form_name'] = form.form_display_name
    return render_to_response(request, template, context)

@extuser_required()
@transaction.commit_manually
def register_xform(request, template='register_and_list_xforms.html'):
    context = {}
    extuser = request.extuser
    if request.method == 'POST':        
        form = RegisterXForm(request.POST, request.FILES)        
        if form.is_valid():
            # must add_schema to storage provide first since forms are dependent upon elements 
            try:
                xformmanager = XFormManager()
                formdefmodel = xformmanager.add_schema(request.FILES['file'].name, request.FILES['file'])
            except Exception, e:
                logging.error(unicode(e))
                context['errors'] = unicode(e)
                transaction.rollback()
            else:
                formdefmodel.submit_ip = request.META['REMOTE_ADDR']
                formdefmodel.bytes_received =  request.FILES['file'].size
                formdefmodel.form_display_name = form.cleaned_data['form_display_name']                
                formdefmodel.uploaded_by = extuser
                if extuser:
                    formdefmodel.domain = extuser.domain
                
                formdefmodel.save()
                logging.debug("xform registered")
                transaction.commit()
                context['newsubmit'] = formdefmodel
        else:
            context['errors'] = form.errors
    context['upload_form'] = RegisterXForm()
    context['registered_forms'] = FormDefModel.objects.all().filter(domain= extuser.domain)
    return render_to_response(request, template, context)

@extuser_required()
@transaction.commit_manually
def submit_data(request, formdef_id, template='submit_data.html'):
    """ A debug utility for admins to submit xml directly to a schema """ 
    context = {}
    extuser = request.extuser
    if request.method == 'POST':
        form = SubmitDataForm(request.POST, request.FILES)        
        if form.is_valid():
            new_submission = do_old_submission(request.META, \
                request.FILES['file'].read(), domain=extuser.domain)
            if new_submission == '[error]':
                logging.error("Domain Submit(): Submission error")
                context['errors'] = "Problem with submitting data"
            else:
                attachments = Attachment.objects.all().filter(submission=new_submission)
                context['submission'] = new_submission
        else:
             logging.error("Domain Submit(): Form submission error")
             context['errors'] = form.errors
    context['upload_form'] = SubmitDataForm()
    return data(request, formdef_id, template, context)

@transaction.commit_manually
def reregister_xform(request, domain_name, template='register_and_list_xforms.html'):
    # registers an xform without having a user context, for 
    # server-generated submissions
    context = {}
    extuser = None
    if request.user:
        try:
            extuser = ExtUser.objects.all().get(id=request.user.id)
        except ExtUser.DoesNotExist:
            # we don't really care about this.
            # czue: then why is this whole check here?
            pass
    if request.method == 'POST':        
        # must add_schema to storage provide first since forms are dependent upon elements 
        try:
            metadata = request.META
            domain = Domain.objects.get(name=domain_name)
            type = metadata["HTTP_SCHEMA_TYPE"]
            schema = request.raw_post_data
            xformmanager = XFormManager()
            formdefmodel = xformmanager.add_schema_manual(schema, type)
        except IOError, e:
            logging.error("xformmanager.manager: " + unicode(e) )
            context['errors'] = "Could not convert xform to schema. Please verify correct xform format."
            context['upload_form'] = RegisterXForm()
            context['registered_forms'] = FormDefModel.objects.all().filter(domain= extuser.domain)
            return render_to_response(request, template, context)
        except Exception, e:
            logging.error(e)
            logging.error("Unable to write raw post data<br/>")
            logging.error("Unable to write raw post data: Exception: " + unicode(sys.exc_info()[0]) + "<br/>")
            logging.error("Unable to write raw post data: Traceback: " + unicode(sys.exc_info()[1]))
            type, value, tb = sys.exc_info()
            logging.error(unicode(type.__name__), ":", unicode(value))
            logging.error("error parsing attachments: Traceback: " + '\n'.join(traceback.format_tb(tb)))
            logging.error("Transaction rolled back")
            context['errors'] = "Unable to write raw post data" + unicode(sys.exc_info()[0]) + unicode(sys.exc_info()[1])
            transaction.rollback()                            
        else:
            formdefmodel.submit_ip = metadata['HTTP_ORIGINAL_SUBMIT_IP']
            formdefmodel.bytes_received =  metadata['CONTENT_LENGTH']
            formdefmodel.form_display_name = metadata['HTTP_FORM_DISPLAY_NAME']                
            formdefmodel.uploaded_by = extuser
            formdefmodel.domain = domain
            # we have the rest of the info in the metadata, but for now we
            # won't use it
            formdefmodel.save()                
            logging.debug("xform registered")
            transaction.commit()                
            context['register_success'] = True
            context['newsubmit'] = formdefmodel
            return HttpResponse("Thanks for submitting!  That worked great.  Form: %s" % formdefmodel)
    return HttpResponse("Not sure what happened but either you didn't give us a schema or something went wrong...")

@login_required()
def single_xform(request, formdef_id, template_name="single_xform.html"):
    context = {}    
    show_schema = False
    for item in request.GET.items():
        if item[0] == 'show_schema':
            show_schema = True           
    xform = FormDefModel.objects.all().filter(id=formdef_id)
    
    if show_schema:
        response = HttpResponse(mimetype='text/xml')
        fin = open(xform[0].xsd_file_location ,'r')
        txt = fin.read()
        fin.close()
        response.write(txt) 
        return response
    else:    
        context['xform_item'] = xform[0]
        return render_to_response(request, template_name, context)
        
@login_required()
def single_instance(request, formdef_id, instance_id, template_name="single_instance.html"):
    '''
       View data for a single xform instance submission.  
    '''
    xform = FormDefModel.objects.get(id=formdef_id)
    row = xform.get_row(instance_id)
    fields = xform.get_display_columns()
    # make them a list of tuples of field, value pairs for easy iteration
    data = zip(fields, row)
    return render_to_response(request, template_name, {"form" : xform,
                                                       "id": instance_id,  
                                                       "data": data })
        
@login_required()
def single_instance_csv(request, formdef_id, instance_id):
    '''
       CSV dowload for data for a single xform instance submission.  
    '''
    # unfortunate copy pasting of the above method.   
    xform = FormDefModel.objects.get(id=formdef_id)
    row = xform.get_row(instance_id)
    fields = xform.get_display_columns()
    data = zip(fields, row)
    
    output = StringIO()
    w = UnicodeWriter(output)
    headers = ["Field", "Value"]
    w.writerow(headers)
    for row in data:
        w.writerow(row)
    output.seek(0)
    response = HttpResponse(output.read(),
                        mimetype='application/ms-excel')
    response["content-disposition"] = 'attachment; filename="%s-%s.csv"' % ( xform.form_display_name, instance_id)
    return response


@login_required()
def export_xml(request, formdef_id):
    """
    Get a zip file containing all submissions for this schema
    """
    formdef = get_object_or_404(FormDefModel, pk=formdef_id)
    metadata = Metadata.objects.filter(formdefmodel=formdef).order_by('id')
    file_list = []
    for datum in metadata:
        file_list.append( datum.submission.filepath )
    return get_zipfile(file_list)

@extuser_required()
def data(request, formdef_id, template_name="data.html", context={}):
    '''View the xform data for a particular schema.  Accepts as
       url parameters the following (with defaults specified):
       items: 25 (the number of items to paginate at a time
       page: 1 (the page you are on)
       sort_column: id (?) (the column to sort by)
       sort_descending: True (?) (the sort order of the column)
       ''' 
    xform = get_object_or_404(FormDefModel, id=formdef_id)
    # extract params
    items = 25
    sort_column = "id" # todo: see if we can sort better by default
    columns = xform.get_column_names()
    sort_descending = True
    if "items" in request.GET:
        try:
            items = int(request.GET["items"])
        except Exception:
            # just default to the above if we couldn't 
            # parse it
            pass
    if "sort_column" in request.GET:
        if request.GET["sort_column"] in columns:
            sort_column = request.GET["sort_column"]
        else:
            context["errors"] = "Sorry, we currently can't sort by the column '%s' and have sorted by the default column, '%s', instead."  %\
                                (request.GET["sort_column"], sort_column)
    if "sort_descending" in request.GET:
        # a very dumb boolean parser
        sort_descending_str = request.GET["sort_descending"]
        if sort_descending_str.startswith("f"):
            sort_descending = False
        else:
            sort_descending = True
    
    
        
    rows = xform.get_rows(sort_column=sort_column, sort_descending=sort_descending)
    context["sort_index"] = columns.index(sort_column)
    context['columns'] = columns 
    context['form_name'] = xform.form_name
    context['xform'] = xform
    context['sort_descending'] = sort_descending
    context['data'] = paginate(request, rows, rows_per_page=items)
    # python! rebuild the query string, removing the "page" argument so it can
    # be passed on when paginating.
    
    context['param_string_no_page'] = "&".join(['%s=%s' % (key, value)\
                                                for key, value in request.GET.items()\
                                                if key != "page"])
    return render_to_response(request, template_name, context)

@extuser_required()
@transaction.commit_manually
def delete_data(request, formdef_id, template='confirm_multiple_delete.html'):
    context = {}
    extuser = request.extuser
    form = get_object_or_404(FormDefModel, pk=formdef_id)
    if request.method == "POST":
        if 'instance' in request.POST:
            request.session['xform_data'] = [] 
            metadata = []
            for i in request.POST.getlist('instance'):
                # user has selected items and clicked 'delete'
                # redirect to confirmation
                if 'checked_'+ i in request.POST:
                    meta = Metadata.objects.get(formdefmodel=form, raw_data=int(i))
                    metadata.append(meta)
                    request.session['xform_data'].append(int(i))
                context['xform_data'] = metadata
        elif 'confirm_delete' in request.POST: 
            # user has confirmed deletion. Proceed.
            xformmanager = XFormManager()
            for id in request.session['xform_data']:
                xformmanager.remove_data(formdef_id, id)
            logging.debug("Instances %s of schema %s were deleted.", \
                          (unicode(request.session['xform_data']), formdef_id))
            request.session['xform_data'] = None
            return HttpResponseRedirect( reverse("xformmanager.views.data", \
                                         args=[formdef_id]) )
    else:
        request.session['xform_data'] = None
    context['form_name'] = form.form_display_name
    context['formdef_id'] = formdef_id
    return render_to_response(request, template, context)

@extuser_required()
def export_csv(request, formdef_id):
    xsd = get_object_or_404( FormDefModel, pk=formdef_id)
    return format_csv(xsd.get_rows(), xsd.get_column_names(), xsd.form_name)
    
def get_csv_from_form(formdef_id, form_id=0, filter=''):
    try:
        xsd = FormDefModel.objects.get(id=formdef_id)
    except FormDefModel.DoesNotExist:
        return HttpResponseBadRequest("Schema with id %s not found." % formdef_id)
    cursor = connection.cursor()
    row_count = 0
    if form_id == 0:
        try:
            query= 'SELECT * FROM ' + xsd.form_name
            if filter: query = query + " WHERE " + filter
            query = query + ' ORDER BY id'
            cursor.execute(query)
        except Exception, e:
            return HttpResponseBadRequest(\
                "Schema %s could not be queried with query %s" % \
                ( xsd.form_name,query) )        
        rows = cursor.fetchall()
    else:
        try:
            cursor.execute("SELECT * FROM " + xsd.form_name + ' where id=%s', [form_id])
        except Exception, e:
            return HttpResponseBadRequest(\
                "Instance with id %s for schema %s not found." % (form_id,xsd.form_name) )
        rows = cursor.fetchone()
        row_count = 1
    columns = xsd.get_column_names()    
    name = xsd.form_name
    return format_csv(rows, columns, name, row_count)

