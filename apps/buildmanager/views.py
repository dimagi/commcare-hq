import datetime
import os
import logging

from django.contrib.auth.models import User
from hq.utils import build_url
from domain.models import Domain
from domain.decorators import login_and_domain_required
from requestlogger.models import RequestLog
from xformmanager.manager import readable_form, csv_dump

from buildmanager.exceptions import BuildError
from buildmanager.models import *
from buildmanager.forms import *
from buildmanager.jar import validate_jar
from buildmanager import xformvalidator

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
    if request.user.selected_domain:
        context['projects'] = Project.objects.filter(domain=request.user.selected_domain)
    else:
        context['projects'] = Project.objects.all()
    return render_to_response(request, template_name, context)

    
@login_required()
def show_project(request, project_id, template_name="buildmanager/show_project.html"):    
    context = {}
    try:
        project = Project.objects.get(id=project_id)
        context['project'] = project
        context['build_map'] = _get_single_project_builds(project)
        context['latest_build'] = project.get_latest_released_build()
    except:
        raise Http404    
    return render_to_response(request, template_name, context)

@login_and_domain_required
def all_builds(request, template_name="buildmanager/all_builds.html"):    
    context = {}    
    domain = request.user.selected_domain
    projects = Project.objects.filter(domain=domain)
    builds = _get_build_dictionary(projects)
    context['all_builds'] = builds
    return render_to_response(request, template_name, context)

def _get_build_dictionary(projects):
    builds = {}
    for project in projects:
        builds[project] = _get_single_project_builds(project)
    return builds  

def _get_single_project_builds(project):
    this_project_dict = {}
    this_project_dict["normal"] = project.get_non_released_builds()
    this_project_dict["release"] = project.get_released_builds()
    return this_project_dict
        
def show_latest_build(request, project_id, template_name="buildmanager/show_build.html"):
    context = {}
    try:
        project = Project.objects.get(id=project_id)
    except Project.DoesNotExist:
        raise Http404
    build = project.get_latest_released_build()
    context['build'] = build
    return render_to_response(request, template_name, context)

@login_required()
def show_build(request, build_id, template_name="buildmanager/show_build.html"):
    context = {}
    try:
        context['build'] = ProjectBuild.objects.get(id=build_id)
    except:
        raise Http404
    return render_to_response(request, template_name, context)


def get_buildfile(request, project_id, build_number, filename, template_name=None):    
    """For a given build, we now have a direct and unique download URL for it 
       within a given project. This will directly stream the file to the 
       browser.  This is because we want to track download counts    
    """
    try:
        proj = Project.objects.get(id=project_id)
        build = ProjectBuild.objects.filter(project=proj).get(build_number=build_number)
        return _get_buildfile(request, proj, build, filename)
    except Exception, e:
        return _handle_error(request,
                             "problem accessing build/file: %s/%s for project: %s. error is: %s" % 
                             (build_number, filename, project_id, e))
       
def get_latest_buildfile(request, project_id, filename, template_name=None):
    '''Gets the latest released build file for a given project'''
    try:
        proj = Project.objects.get(id=project_id)
    except Project.DoesNotExist:
        raise Http404
    build = proj.get_latest_released_build() 
    if build:
        return _get_buildfile(request, proj, build, filename)
    else:
        raise Http404
        
def _get_buildfile(request, project, build, filename):    
    returndata = None
    
    if filename.endswith('.jar'):
        fpath = build.get_jar_filename()
        if fpath != filename:
            raise Http404
        
        mtype = mimetypes.guess_type(build.jar_file)[0]
        fin = build.get_jar_filestream()
        if not fin:
            raise Http404
        _log_build_download(request, build, "jar")
        returndata = fin.read()
        fin.close()
        
    elif filename.endswith('.jad'):
        fpath = build.get_jad_filename()
        mtype = mimetypes.guess_type(build.jad_file)[0]            
        if fpath != filename:
            raise Http404
        fin = build.get_jad_filestream()
        if not fin:
            raise Http404
        _log_build_download(request, build, "jad")        
        returndata = fin.read()     
        fin.close()   
        
    elif filename.endswith('.zip'):        
        mtype = "application/zip"
        returndata = build.get_zip_filestream()
        if not returndata:
            raise Http404
        _log_build_download(request, build, "zip")        
    
    if mtype == None:
        response = HttpResponse(mimetype='text/plain')
    else:
        response = HttpResponse(mimetype=mtype)
    response.write(returndata)    
    return response

def _log_build_download(request, build, type):
    '''Logs and saves a build download.'''
    log = RequestLog.from_request(request)
    log.save()
    download = BuildDownload(type=type, build=build, log=log)
    download.save()
    # Also add a little notifier here so we can track build downloads
    if (hasattr(request, "user")):
        user_display = str(request.user)
    else:
        user_display = "An anonymous user"
    logging.error("Hey! %s just downloaded the %s file for build %s!  The request was a %s"\
                   %(user_display, type, build.get_display_string(), log))
    
def _log_build_upload(request, build):
    '''Logs and saves a build upload.'''
    log = RequestLog.from_request(request)
    log.save()
    upload = BuildUpload(build=build, log=log)
    upload.save()
    
@login_required
def release(request, build_id, template_name="buildmanager/release_confirmation.html"): 
    try: 
        build = ProjectBuild.objects.get(id=build_id)
    except ProjectBuild.DoesNotExist:
        raise Http404
    try:
        build.release(request.user)
        context = {}
        context["build"] = build
        context["jad_url"] =  build_url(build.get_jad_downloadurl(), request)
        context["latest_url"] = build_url(build.project.get_latest_jad_url(), request)
         
        return render_to_response(request, template_name, context)
    except BuildError, e:
        error_string = "Problem releasing build: %s, the errors are as follows:<br><br>%s" % (build, e.get_error_string("<br><br>"))
        return _handle_error(request, error_string)
    except Exception, e:
        # we may want to differentiate from expected (BuildError) and unexpected
        # (everything else) errors down the road, for now we treat them the same.
        error_string = "Problem releasing build: %s, the error is: %s" % (build.get_display_string(), unicode(e)) 
        return _handle_error(request, error_string)
        


@login_required
def new_build(request, template_name="buildmanager/new_build.html"): 
    context = {}
    form = ProjectBuildForm()    
    if request.method == 'POST':
        form = ProjectBuildForm(request.POST, request.FILES)                
        if form.is_valid():
            try:                      
                newbuild = form.save(commit=False)
                newbuild.uploaded_by=request.user
                newbuild.description = urllib.unquote(newbuild.description)
                newbuild.package_created = datetime.datetime.now()
                newbuild.set_jadfile(request.FILES['jad_file_upload'].name, request.FILES['jad_file_upload'])
                newbuild.set_jarfile(request.FILES['jar_file_upload'].name, request.FILES['jar_file_upload'])
                newbuild.save()
                _log_build_upload(request, newbuild)
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

@login_required
def get_build_xform(request, id, template_name="buildmanager/display_xform.html"):
    form = BuildForm.objects.get(id=id)
    if "download" in request.GET:
        fin = form.as_filestream()
        # unfortunately, neither of these more correct displays actually look good in firefox
        #response = HttpResponse(fin.read(), mimetype='application/xhtml+xml')
        #response = HttpResponse(fin.read(), mimetype='text/xml')
        response = HttpResponse(fin.read(), mimetype='text/xml')
        response["content-disposition"] = 'attachment; filename=%s' % form.get_file_name()
        fin.close()
        return response
    else:
        # display it inline on HQ
        return render_to_response(request, template_name, { "xform": form })

@login_required
def translation_csv(req, id):
    """Get csv of the translation file for an xform"""
    form = BuildForm.objects.get(id=id)
    xform_body = form.get_text()
    try:
        result, errors, has_error = csv_dump(xform_body)
        response = HttpResponse(result,
                        mimetype='application/ms-excel')
        response["content-disposition"] = 'attachment; filename="%s-translations.csv"' % ( form.get_file_name())
        return response
    except Exception, e:
        return _handle_error(req, e.message)
    
    

def readable_xform(req, template_name="buildmanager/readable_form_creator.html"):
    """Get a readable xform"""
    
    def get(req, template_name):
        return render_to_response(req, template_name, {})
    
    def post(req, template_name):
        xform_body = req.POST["xform"]
        try:
            result, errors, has_error = readable_form(xform_body)
            return render_to_response(req, template_name, {"success": True, 
                                                           "message": "Your form was successfully validated!",
                                                           "xform": xform_body,
                                                           "readable_form": result
                                                           })
        except Exception, e:
            return render_to_response(req, template_name, {"success": False, 
                                                           "message": "Failure to generate readable xform! %s" % e,
                                                           "xform": xform_body
                                                           })
        
    
    # invoke the correct function...
    # this should be abstracted away
    if   req.method == "GET":  return get(req, template_name)
    elif req.method == "POST": return post(req, template_name)        
    

def validator(req, template_name="buildmanager/validator.html"):
    """Validate an xform"""
    
    def get(req, template_name):
        return render_to_response(req, template_name, {})
    
    def post(req, template_name):
        xform_body = req.POST["xform"]
        hq_validation = True if "hq-validate" in req.POST else False
        try:
            xformvalidator.validate_xml(xform_body, do_hq_validation=hq_validation)
            return render_to_response(req, template_name, {"success": True, 
                                                           "message": "Your form was successfully validated!",
                                                           "xform": xform_body
                                                           })
        except Exception, e:
            return render_to_response(req, template_name, {"success": False, 
                                                           "message": "Validation Fail! %s" % e,
                                                           "xform": xform_body
                                                           })
        
    
    # invoke the correct function...
    # this should be abstracted away
    if   req.method == "GET":  return get(req, template_name)
    elif req.method == "POST": return post(req, template_name)        
    
def _handle_error(request, error_message):
    """Handles an error, by logging it and returning a 500 page"""
    logging.error(error_message)
    return render_to_response(request, "500.html", {"error_message" : error_message})
