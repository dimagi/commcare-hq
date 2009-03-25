from django.shortcuts import render_to_response, get_object_or_404
from django.http import HttpResponse
from django.template import RequestContext
from django.db import transaction
import uuid
import hashlib

from xformmanager.forms import RegisterXForm
from xformmanager.models import FormDefData
from xformmanager.xformdef import * 
from xformmanager.xformdata import *
from xformmanager.storageutility import * 
import settings, os, sys
import logging

#temporary
from lxml import etree

from StringIO import StringIO

from submitlogger.models import Attachment
from django.db.models.signals import post_save

# Register to receive signals from submitlogger
post_save.connect(process, sender=Attachment)

def process(sender, **kwargs): #get sender, instance, created
    xml_file_name = kwargs["instance"].filepath
    su = StorageUtility()
    su.save_form_data(xml_file_name)
    
def register_xform(request, template='register_and_list_xforms.html'):
    context = {}
    if request.method == 'POST':
        form = RegisterXForm(request.POST, request.FILES)
        if form.is_valid():
            transaction = str(uuid.uuid1())
            try:
                logging.debug("temporary file name is " + transaction)                
                new_file_name = __file_name(transaction)
                logging.debug("try to write file")
                fout = open(new_file_name, 'w')
                fout.write( request.FILES['file'].read() )
                fout.close()
                
                #process xsd file to FormDef object
                fout = open(new_file_name, 'r')
                formdef_provider = FormDefProviderFromXSD(fout)
                fout.close()
                formdef = formdef_provider.get_formdef()
                
                #create dynamic tables
                storage_provider = FormStorageProvider()
                element_id = storage_provider.add_formdef(formdef)
                
                fdd = FormDefData()
                fdd.transaction_uuid = transaction
                fdd.submit_ip = request.META['REMOTE_ADDR']
                fdd.raw_header = repr(request.META)
                fdd.checksum = hashlib.md5(request.raw_post_data).hexdigest()
                fdd.bytes_received =  request.FILES['file'].size
                
                fdd.form_name = formdef.name
                fdd.target_namespace = formdef.target_namespace
                fdd.element_id = element_id
                fdd.xsd_file_location = new_file_name
                fdd.save() 
                
                logging.debug("xform registered")
            except:
                logging.error("Unable to write raw post data")
                logging.error("Unable to write raw post data: Exception: " + str(sys.exc_info()[0]))
                logging.error("Unable to write raw post data: Traceback: " + str(sys.exc_info()[1]))
                context['errors'] = "Unable to write raw post data" + str(sys.exc_info()[0]) + str(sys.exc_info()[1])
    context['upload_form'] = RegisterXForm()
    context['registered_forms'] = FormDefData.objects.all()
    return render_to_response(template, context, context_instance=RequestContext(request))

def single_xform(request, submit_id, template_name="single_xform.html"):
    context = {}        
    xform = FormDefData.objects.all().filter(id=submit_id)
    context['xform_item'] = xform[0]
    rawstring = str(xform[0].raw_header)
    rawstring = rawstring.replace(': <',': "<')
    rawstring = rawstring.replace('>,','>",')
    processed_header = eval(rawstring)
    return render_to_response(template_name, context, context_instance=RequestContext(request))
    #return HttpResponse("YES")

def __file_name(name):
    return os.path.join(settings.XSD_REPOSITORY_PATH, str(name) + '.postdata')

#temporary measure to get target form
#decide later whether this is better, or should we know from the url?
def __get_xmlns(stream):
    #skip junk line
    tree = etree.parse(stream)
    root = tree.getroot()
    r = re.search('{[a-zA-Z0-9\.\/\:]*}', root.tag)
    xmlns = r.group(0).strip('{').strip('}')
    return xmlns

""" UNUSED. For now.

def list_posted(request):
    return show_submits(request, "list_posted.html")

def show_xml(request, submit_id):
    return single_submission(request, submit_id, "show_xml.html")

def list_xforms(request, template_name="list_xforms.html"):
    context = {}
    context['registered_forms'] = FormDefData.objects.all()  
    return render_to_response(template_name, context, context_instance=RequestContext(request))

"""
