import datetime
import os
import logging

from hq.models import ExtUser
from hq.models import Domain

from buildmanager.models import *
from buildmanager.forms import *

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
def all_projects(request, template_name="buildmanager/all_projects.html"):    
    context = {}    
    try: 
        extuser = ExtUser.objects.all().get(id=request.user.id)
        context['projects'] = Project.objects.filter(domain=extuser.domain)
    except:
        context['projects'] = Project.objects.all()    
    return render_to_response(request, template_name, context)

    
@login_required()
def show_project(request, project_id, template_name="buildmanager/show_project.html"):    
    context = {}
    try:
        context['project'] = Project.objects.get(id=project_id)
        context['builds'] = ProjectBuild.objects.filter(project=context['project']).order_by('-package_created')
    except:
        raise Http404    
    return render_to_response(request, template_name, context)

@login_required()
def all_builds(request, template_name="buildmanager/all_builds.html"):    
    context = {}    
    try: 
        extuser = ExtUser.objects.all().get(id=request.user.id)
        context['builds'] = ProjectBuild.objects.filter(project__domain=extuser.domain).order_by('-package_created')
    except ExtUser.DoesNotExist:
        context['builds'] = ProjectBuild.objects.all().order_by('-package_created')
    return render_to_response(request, template_name, context)


@login_required()
def project_builds(request, template_name="buildmanager/all_builds.html"):    
    context = {}
    try: 
        extuser = ExtUser.objects.all().get(id=request.user.id)
    except ExtUser.DoesNotExist:
        template_name="hq/no_permission.html"
        return render_to_response(template_name, context, context_instance=RequestContext(request))    

    
    try:
        context['builds'] = ProjectBuild.objects.filter(project__domain=extuser.domain).order_by('-package_created')
    except:
        raise Http404
    return render_to_response(request, template_name, context)
    
    
@login_required()
def show_build(request, build_id, template_name="buildmanager/show_build.html"):    
    context = {}
    try:
        context['builds'] = ProjectBuild.objects.get(id=build_id)
    except:
        raise Http404
    return render_to_response(request, template_name, context)



@login_required()
def get_buildfile(request,project_id, build_number, filename, template_name=None):    
    """For a given build, we now have a direct and unique download URL for it within a given project
    This will directly stream the file to the browser.  This is because we want to track download counts    
    """
    try:
        proj = Project.objects.get(id=project_id)
        build = ProjectBuild.objects.filter(project=proj).get(build_number=build_number)
        print proj
        print build
        
        if filename.endswith('.jar'):
            fpath = os.path.basename(build.jar_file)
            print fpath
            if fpath != filename:
                raise Http404
            
            
            mtype = mimetypes.guess_type(build.jar_file)[0]
            build.jar_download_count += 1
            fin = build.get_jar_filestream()            
            
        elif filename.endswith('.jad'):
            fpath = os.path.basename(build.jad_file)
            print fpath
            mtype = mimetypes.guess_type(build.jad_file)[0]            
            if fpath != filename:
                raise Http404
            
            build.jad_download_count += 1
            fin = build.get_jad_filestream()        
        if mtype == None:
            response = HttpResponse(mimetype='text/plain')
        else:
            response = HttpResponse(mimetype=mtype)
        response.write(fin.read())
        fin.close() 
        build.save()
        
        return response
    except Exception, e:
        print e        
        raise Http404
       
    
    


@login_required
def new_build(request, template_name="buildmanager/new_build.html"): 
    context = {}
    form = BuildForm()    
    if request.method == 'POST':
        form = BuildForm(request.POST, request.FILES)                
        if form.is_valid():
            # must add_schema to storage provide first since forms are dependent upon elements            
            try:                      
                newbuild = form.save(commit=False)
                newbuild.uploaded_by=request.user
                newbuild.description = urllib.unquote(newbuild.description)
                newbuild.package_created = datetime.datetime.now()
                newbuild.set_jadfile(request.FILES['jad_file_upload'].name, request.FILES['jad_file_upload'])
                newbuild.set_jarfile(request.FILES['jar_file_upload'].name, request.FILES['jar_file_upload'])
                newbuild.save()                
                return HttpResponseRedirect(reverse('buildmanager.views.all_builds'))
            except Exception, e:
                logging.error("buildmanager new ProjectBuild creation error.", 
                              extra={'exception':e, 
                                     'request.POST': request.POST, 
                                     'request.FILES': request.FILES, 
                                     'form':form})
                context['errors'] = "Could not commit build: " + str(e)
    
    
    context['form'] = form
    return render_to_response(request, template_name, context)


