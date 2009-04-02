from django.shortcuts import render_to_response, get_object_or_404
from django.http import HttpResponse
from django.template import RequestContext
from django.db import transaction
import uuid
import hashlib

from xformmanager.forms import RegisterXForm
from xformmanager.models import FormDefData
from xformmanager.xformdef import FormDef
from xformmanager.storageutility import * 
from xformmanager.csv import generate_CSV
import settings, os, sys
import logging
import traceback
import subprocess

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
    
def register_xform(request, template='register_and_list_xforms.html'):
    context = {}
    if request.method == 'POST':
        form = RegisterXForm(request.POST, request.FILES)
        if form.is_valid():
            transaction = str(uuid.uuid1())
            try:
                logging.debug("temporary file name is " + transaction)                

                new_file_name = __xsd_file_name(transaction)
                if request.FILES['file'].name.endswith("xsd"):
                    fout = open(new_file_name, 'w')
                    fout.write( request.FILES['file'].read() )
                    fout.close()
                else: 
                    #user has uploaded an xhtml/xform file
                    xform_file_name = __xform_file_name(transaction)
                    fout = open(xform_file_name, 'w')
                    fout.write( request.FILES['file'].read() )
                    fout.close()
                    logging.debug ("java -jar form_translate.jar schema < " + xform_file_name + ">" + new_file_name)
                    retcode = subprocess.call(["java","-jar",os.path.join(settings.SCRIPT_PATH,"form_translate.jar"),"schema","<",xform_file_name,">",new_file_name],shell=True)  
                    if retcode == 1:
                        context['errors'] = request.FILES['file'].name+" could not be processed"
                        raise Exception(request.FILES['file'].name+" could not be processed")
                        
                #process xsd file to FormDef object
                fout = open(new_file_name, 'r')
                formdef = FormDef(fout)
                fout.close()
                
                #create dynamic tables
                # must add_formdef to storage provide first since forms are linked to elements 
                storage_provider = StorageUtility()
                element_id = storage_provider.add_formdef(formdef)
                
                fdd = FormDefData()
                fdd.submit_ip = request.META['REMOTE_ADDR']
                fdd.bytes_received =  request.FILES['file'].size
                
                fdd.form_name = get_table_name(formdef.target_namespace)
                fdd.target_namespace = formdef.target_namespace
                fdd.element_id = element_id
                fdd.xsd_file_location = new_file_name
                fdd.save() 
                
                logging.debug("xform registered")
            except Exception, e:
                logging.error(e)
                logging.error("Unable to write raw post data<br/>")
                logging.error("Unable to write raw post data: Exception: " + str(sys.exc_info()[0]) + "<br/>")
                logging.error("Unable to write raw post data: Traceback: " + str(sys.exc_info()[1]))
                type, value, tb = sys.exc_info()
                logging.error(type.__name__, ":", value)
                logging.error("error parsing attachments: Traceback: " + '\n'.join(traceback.format_tb(tb)))
                context['errors'] = "Unable to write raw post data" + str(sys.exc_info()[0]) + str(sys.exc_info()[1])
    context['upload_form'] = RegisterXForm()
    context['registered_forms'] = FormDefData.objects.all()
    return render_to_response(template, context, context_instance=RequestContext(request))

def single_xform(request, formdef_name, template_name="single_xform.html"):
    context = {}        
    xform = FormDefData.objects.all().filter(form_name=formdef_name)
    context['xform_item'] = xform[0]
    return render_to_response(template_name, context, context_instance=RequestContext(request))
    #return HttpResponse("YES")

def data(request, formdef_name, template_name="data.html"):
    context = {}
    cursor = connection.cursor()
    cursor.execute("SELECT * FROM " + formdef_name)
    rows = cursor.fetchall()
    
    rawcolumns = cursor.description # in ((name,,,,,),(name,,,,,)...)
    context['columns'] = []
    for col in rawcolumns:
        context['columns'].append(col[0])    
    context['form_name'] = formdef_name
    context['data'] = []
    for row in rows:
        record = []
        for field in row:
            record.append(field)
        context['data'].append(record)
    file_name = formdef_name+".csv"
    if os.path.exists( os.path.join(settings.CSV_PATH,file_name ) ):
         context['csv_file'] = file_name
    return render_to_response(template_name, context, context_instance=RequestContext(request))

def __xsd_file_name(name):
    return os.path.join(settings.XSD_REPOSITORY_PATH, str(name) + '-xsd.xml')

def __xform_file_name(name):
    return os.path.join(settings.XSD_REPOSITORY_PATH, str(name) + '-xform.xml')
