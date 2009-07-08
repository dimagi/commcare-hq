from django.http import Http404
from rapidsms.webui.utils import render_to_response
from django.shortcuts import get_object_or_404
from django.http import HttpResponse, HttpResponseRedirect
from django.template import RequestContext
from django.db import transaction, connection
import hashlib
from django.contrib.auth.decorators import login_required
from xformmanager.forms import RegisterXForm
from xformmanager.models import FormDefModel, Case
from xformmanager.xformdef import FormDef
from xformmanager.manager import *
import settings, os, sys
import logging
import traceback
import csv

from django.core.paginator import Paginator, InvalidPage, EmptyPage
from organization.models import *

from StringIO import StringIO

from receiver.models import Attachment
from django.db.models import signals

@login_required()
@transaction.commit_manually
def remove_xform(request, form_id=None, template='confirm_delete.html'):
    context = {}
    extuser = ExtUser.objects.all().get(id=request.user.id)
    
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

@login_required()
@transaction.commit_manually
def register_xform(request, template='register_and_list_xforms.html'):
    context = {}
    if ExtUser.objects.all().filter(id=request.user.id).count() == 0:
        template_name="organization/no_permission.html"
        return render_to_response(request, template_name, context)
    extuser = ExtUser.objects.all().get(id=request.user.id)
    if request.method == 'POST':        
        form = RegisterXForm(request.POST, request.FILES)        
        if form.is_valid():
            # must add_schema to storage provide first since forms are dependent upon elements 
            try:
                xformmanager = XFormManager()
                formdefmodel = xformmanager.add_schema(request.FILES['file'].name, request.FILES['file'])
            except IOError, e:
                logging.error("xformmanager.manager: " + str(e) )
                context['errors'] = "Could not convert xform to schema. Please verify correct xform format."
                context['upload_form'] = RegisterXForm()
                context['registered_forms'] = FormDefModel.objects.all().filter(domain= extuser.domain)
                return render_to_response(request, template, context)
            except Exception, e:
                logging.error(e)
                logging.error("Unable to write raw post data<br/>")
                logging.error("Unable to write raw post data: Exception: " + str(sys.exc_info()[0]) + "<br/>")
                logging.error("Unable to write raw post data: Traceback: " + str(sys.exc_info()[1]))
                type, value, tb = sys.exc_info()
                logging.error(str(type.__name__), ":", str(value))
                logging.error("error parsing attachments: Traceback: " + '\n'.join(traceback.format_tb(tb)))
                logging.error("Transaction rolled back")
                context['errors'] = "Unable to write raw post data" + str(sys.exc_info()[0]) + str(sys.exc_info()[1])
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
                context['register_success'] = True
                context['newsubmit'] = formdefmodel
    context['upload_form'] = RegisterXForm()
    context['registered_forms'] = FormDefModel.objects.all().filter(domain= extuser.domain)
    return render_to_response(request, template, context)

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
            logging.error("xformmanager.manager: " + str(e) )
            context['errors'] = "Could not convert xform to schema. Please verify correct xform format."
            context['upload_form'] = RegisterXForm()
            context['registered_forms'] = FormDefModel.objects.all().filter(domain= extuser.domain)
            return render_to_response(request, template, context)
        except Exception, e:
            logging.error(e)
            logging.error("Unable to write raw post data<br/>")
            logging.error("Unable to write raw post data: Exception: " + str(sys.exc_info()[0]) + "<br/>")
            logging.error("Unable to write raw post data: Traceback: " + str(sys.exc_info()[1]))
            type, value, tb = sys.exc_info()
            logging.error(str(type.__name__), ":", str(value))
            logging.error("error parsing attachments: Traceback: " + '\n'.join(traceback.format_tb(tb)))
            logging.error("Transaction rolled back")
            context['errors'] = "Unable to write raw post data" + str(sys.exc_info()[0]) + str(sys.exc_info()[1])
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
def data(request, formdef_id, template_name="data.html"):
    context = {}
    
    xform = FormDefModel.objects.get(id=formdef_id)
    rows = xform.get_all_rows()
    context['columns'] = xform.get_column_names()
    
    context['form_name'] = xform.form_name
    context['data'] = []
    context['xform'] = xform
    
    paginator = Paginator(rows, 25) 

    #get the current page number
    try:
        page = int(request.GET.get('page', '1'))
    except ValueError:
        page = 1
    
    try:
        data_pages = paginator.page(page)
    except (EmptyPage, InvalidPage):
        data_pages = paginator.page(paginator.num_pages)
    
    context['data'] = data_pages    
    
    return render_to_response(request, template_name, context)    



@login_required()
def export_csv(request, formdef_id):
    context = {}
    xform = FormDefModel.objects.get(id=formdef_id)

    cursor = connection.cursor()
    cursor.execute("SELECT * FROM " + xform.form_name + ' order by id')
    rows = cursor.fetchall()
    
    columns = xform.get_column_names()
    
    output = StringIO()
    w = csv.writer(output)
    w.writerow(columns)
    for row in rows:
        w.writerow(row)
    # rewind the virtual file
    output.seek(0)
    response = HttpResponse(output.read(),
                        mimetype='application/ms-excel')
    response["content-disposition"] = 'attachment; filename="%s-%s.csv"' % (xform.form_name, str(datetime.now().date()))
    return response
    
@login_required()
def case_reports(request, template_name="case_reports.html"):
    # not sure where this view will live in the UI yet
    context = {}
    if ExtUser.objects.all().filter(id=request.user.id).count() == 0:
        template_name="organization/no_permission.html"
        return render_to_response(request, template_name, context)
    extuser = ExtUser.objects.all().get(id=request.user.id)
    
    context['case_reports'] = Case.objects.filter(domain=extuser.domain)
    context['domain'] = extuser.domain
    return render_to_response(request, template_name, context)

@login_required()
def case_data(request, case_id, template_name="case_data.html"):
    context = {}
    if ExtUser.objects.all().filter(id=request.user.id).count() == 0:
        template_name="organization/no_permission.html"
        return render_to_response(request, template_name, context)
    extuser = ExtUser.objects.all().get(id=request.user.id)
    case = Case.objects.get(id=case_id)
    
    context['cols'] = case.get_column_names()
    
    data = case.get_all_data()
    keys = data.keys()
    keys.sort()
    flattened = []
    for key in keys:
        flattened.append(data[key])
    
    paginator = Paginator(flattened, 25) 
    try:
        page = int(request.GET.get('page', '1'))
    except ValueError:
        page = 1
    try:
        data_pages = paginator.page(page)
    except (EmptyPage, InvalidPage):
        data_pages = paginator.page(paginator.num_pages)
    
    context['data'] = data_pages    
    context['case'] = case
    
    return render_to_response(request, template_name, context)

@login_required()
def case_export_csv(request, case_id, template_name="case_data.html"):
    case = Case.objects.get(id=case_id)
    cols = case.get_column_names()
    data = case.get_all_data().values()
    output = StringIO()
    w = csv.writer(output)
    w.writerow(cols)
    for row in data:
        w.writerow(row)
    output.seek(0)
    response = HttpResponse(output.read(),
                        mimetype='application/ms-excel')
    response["content-disposition"] = 'attachment; filename="%s-%s.csv"' % ( case.name, str(datetime.now().date()))
    return response
