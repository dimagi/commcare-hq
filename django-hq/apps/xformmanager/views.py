from django.http import Http404
from django.shortcuts import render_to_response, get_object_or_404
from django.http import HttpResponse, HttpResponseRedirect
from django.template import RequestContext
from django.db import transaction
import uuid
import hashlib
from django.contrib.auth.decorators import login_required
from xformmanager.forms import RegisterXForm
from xformmanager.models import FormDefData
from xformmanager.xformdef import FormDef
from xformmanager.storageutility import * 
from xformmanager.csv import generate_CSV
import settings, os, sys
import logging
import traceback
import subprocess
from subprocess import PIPE

from django.core.paginator import Paginator, InvalidPage, EmptyPage
from organization.models import *

#temporary
from lxml import etree

from StringIO import StringIO

from receiver.models import Attachment
from django.db.models.signals import post_save
from django.db.models import signals

def process(sender, instance, **kwargs): #get sender, instance, created
    xml_file_name = instance.filepath
    logging.debug("PROCESS: Loading xml data from " + xml_file_name)
    su = StorageUtility()
    table_name = su.save_form_data(xml_file_name)
    generate_CSV(table_name)
    
# Register to receive signals from receiver
post_save.connect(process, sender=Attachment)

@login_required()
@transaction.commit_manually
def remove_xform(request, form_id=None, template='confirm_delete.html'):
    context = {}
    extuser = ExtUser.objects.all().get(id=request.user.id)
    
    form = get_object_or_404(FormDefData, pk=form_id)
    
    if request.method == "POST":
        if request.POST["confirm_delete"]: # The user has already confirmed the deletion.
            su = StorageUtility()
            su.remove_schema(form_id)        
            logging.debug("Schema %s deleted ", form_id)
            #self.message_user(request, _('The %(name)s "%(obj)s" was deleted successfully.') % {'name': force_unicode(opts.verbose_name), 'obj': force_unicode(obj_display)})                    
            return HttpResponseRedirect("../register_xform")
    context['form_name'] = form.form_display_name
    return render_to_response(template, context, context_instance=RequestContext(request))

@login_required()
@transaction.commit_manually
def register_xform(request, template='register_and_list_xforms.html'):
    context = {}
    if ExtUser.objects.all().filter(id=request.user.id).count() == 0:
        template_name="organization/no_permission.html"
        return render_to_response(template_name, context, context_instance=RequestContext(request))
    extuser = ExtUser.objects.all().get(id=request.user.id)
    
    
    if request.method == 'POST':        
        form = RegisterXForm(request.POST, request.FILES)        
        if form.is_valid():
            
            transaction_str = str(uuid.uuid1())
            try:
                logging.debug("temporary file name is " + transaction_str)                

                new_file_name = __xsd_file_name(transaction_str)
                if request.FILES['file'].name.endswith("xsd"):
                    fout = open(new_file_name, 'w')
                    fout.write( request.FILES['file'].read() )
                    fout.close()
                else: 
                    #user has uploaded an xhtml/xform file
                    logging.debug ("XFORMMANAGER.VIEWS: begin subprocess - java -jar form_translate.jar schema < " + request.FILES['file'].name + " > " + new_file_name)
                    p = subprocess.Popen(["java","-jar",os.path.join(settings.rapidsms_apps_conf['xformmanager']['script_path'],"form_translate.jar"),'schema'], shell=True, stdout=subprocess.PIPE,stdin=subprocess.PIPE)
                    logging.debug ("XFORMMANAGER.VIEWS: begin communicate with subprocess")
                    (output,error) = p.communicate( request.FILES['file'].read() )
                    logging.debug ("XFORMMANAGER.VIEWS: finish communicate with subprocess")
                    
                    if error is not None:
                        if len(error) > 0:
                            logging.error ("XFORMMANAGER.VIEWS: problem converting xform to xsd: + " + request.FILES['file'].name + "\nerror: " + str(error) )
                    fout = open(new_file_name, 'w')
                    fout.write( output )
                    fout.close()
                #process xsd file to FormDef object
                fout = open(new_file_name, 'r')
                formdef = FormDef(fout)
                fout.close()
                
                #create dynamic tables
                # must add_schema to storage provide first since forms are linked to elements 
                storage_provider = StorageUtility()
                fdd = storage_provider.add_schema(formdef)
                
                fdd.submit_ip = request.META['REMOTE_ADDR']
                fdd.bytes_received =  request.FILES['file'].size
                
                fdd.form_display_name = form.cleaned_data['form_display_name']                
                fdd.uploaded_by = extuser
                
                fdd.xsd_file_location = new_file_name
                fdd.save()                
                logging.debug("xform registered")
                transaction.commit()                
                context['register_success'] = True
                context['newsubmit'] = fdd
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
    context['upload_form'] = RegisterXForm()
    context['registered_forms'] = FormDefData.objects.all().filter(uploaded_by__domain= extuser.domain)
    return render_to_response(template, context, context_instance=RequestContext(request))

@login_required()
def single_xform(request, formdef_id, template_name="single_xform.html"):
    context = {}    
    show_schema = False
    for item in request.GET.items():
        if item[0] == 'show_schema':
            show_schema = True           
    xform = FormDefData.objects.all().filter(id=formdef_id)
    
    if show_schema:
        response = HttpResponse(mimetype='text/xml')
        fin = open(xform[0].xsd_file_location ,'r')
        txt = fin.read()
        fin.close()
        response.write(txt) 
        return response
    else:    
        context['xform_item'] = xform[0]
        return render_to_response(template_name, context, context_instance=RequestContext(request))
        
@login_required()
def data(request, formdef_id, template_name="data.html"):
    context = {}
    xform = FormDefData.objects.all().filter(id=formdef_id)
    formdef_name = xform[0].form_name
    
    cursor = connection.cursor()
    cursor.execute("SELECT * FROM " + formdef_name + ' order by id DESC')
    rows = cursor.fetchall()
    
    rawcolumns = cursor.description # in ((name,,,,,),(name,,,,,)...)
    context['columns'] = []
    for col in rawcolumns:
        context['columns'].append(col[0])    
    context['form_name'] = formdef_name
    context['data'] = []
    context['xform'] = xform[0]
    
        
#    fulldata = []
#    for row in rows:
#        rowrecord = []
#        for field in row:
#            rowrecord.append(field)
#        fulldata.append(rowrecord)


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
    
    file_name = formdef_name+".csv"
    if os.path.exists( os.path.join(settings.rapidsms_apps_conf['xformmanager']['csv_path'],file_name ) ):
         context['csv_file'] = file_name
         
    return render_to_response(template_name, context, context_instance=RequestContext(request))    
    

def __xsd_file_name(name):
    return os.path.join(settings.rapidsms_apps_conf['xformmanager']['xsd_repository_path'], str(name) + '-xsd.xml')

def __xform_file_name(name):
    return os.path.join(settings.rapidsms_apps_conf['xformmanager']['xsd_repository_path'], str(name) + '-xform.xml')
