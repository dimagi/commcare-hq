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


def download(request, filename):
    print "DOWNLOAD: ", filename
    
    
def list(request, template_name="releasemanager/home.html"): 
    context = {'form' : BuildForm(), 'builds': {}}
    context['builds']['unreleased'] = Build.objects.filter(released_by__isnull=True).order_by('-created_at')
    context['builds']['released']   = Build.objects.filter(released_by__isnull=False).order_by('-created_at')
    
    return render_to_response(request, template_name, context)

@login_required()
def make_release(request, id):
    build = Build.objects.get(id=id)
    build.released_by = request.user
    build.save()
    return HttpResponseRedirect(reverse('releasemanager.views.list'))
    
@login_required()
def new(request, template_name="releasemanager/home.html"):
    '''save new Jad & Jar into the system'''
    
    context = {}
    form = BuildForm()    
    if request.method == 'POST':
        form = BuildForm(request.POST, request.FILES)                
        if form.is_valid():
            try:                      
                Build = form.save(commit=False)
                Build.uploaded_by=request.user
                Build.description = urllib.unquote(Build.description)

                Build.save_file(request.FILES['jad_file_upload'])
                Build.save_file(request.FILES['jar_file_upload'])

                Build.save()
                # _log_build_upload(request, newbuild)
                return HttpResponseRedirect(reverse('releasemanager.views.Build_list'))
            except Exception, e:
                logging.error("Build upload error.", 
                              extra={'exception':e, 
                                     'request.POST': request.POST, 
                                     'request.FILES': request.FILES, 
                                     'form':form})
                context['errors'] = "Could not commit Build: " + str(e)
    
    context['form'] = form
    return render_to_response(request, template_name, context)
    