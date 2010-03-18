import datetime
import logging
import os

from django.contrib.auth.models import User
from hq.utils import build_url
from domain.models import Domain
from domain.decorators import login_and_domain_required
from requestlogger.models import RequestLog
from xformmanager.manager import readable_form, csv_dump

# from buildmanager.exceptions import BuildError
# from buildmanager.models import *
# from buildmanager.forms import *
# from buildmanager.jar import validate_jar
# from buildmanager import xformvalidator

from releasemanager.forms import *

from rapidsms.webui.utils import render_to_response

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, HttpResponseRedirect
from django.contrib.auth.models import User
from django.http import *
from django.http import HttpResponse
from django.http import HttpResponseRedirect, Http404
from django.core.urlresolvers import reverse

import mimetypes
import urllib

@login_required()
def core_list(request, template_name="releasemanager/core.html"): 
    context = {} 
    
    context['form'] = CoreForm()
    
    context['builds'] = Core.objects.all().order_by('-created_at')
    
    return render_to_response(request, template_name, context)

def core_new(request, template_name="releasemanager/core.html"):
    '''save new Jad & Jar into the system'''
    
    context = {}
    form = CoreForm()    
    if request.method == 'POST':
        form = CoreForm(request.POST, request.FILES)                
        if form.is_valid():
            try:                      
                core = form.save(commit=False)
                core.uploaded_by=request.user
                core.description = urllib.unquote(core.description)

                core.save_file(request.FILES['jad_file_upload'])
                core.save_file(request.FILES['jar_file_upload'])

                core.save()
                # _log_build_upload(request, newbuild)
                return HttpResponseRedirect(reverse('releasemanager.views.core_list'))
            except Exception, e:
                logging.error("core upload error.", 
                              extra={'exception':e, 
                                     'request.POST': request.POST, 
                                     'request.FILES': request.FILES, 
                                     'form':form})
                context['errors'] = "Could not commit core: " + str(e)
    
    context['form'] = form
    return render_to_response(request, template_name, context)
    