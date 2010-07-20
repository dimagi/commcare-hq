import datetime
import logging
import os
import shutil
import time

from django.contrib.auth.models import User
from hq.utils import build_url
from domain.models import Domain
from domain.decorators import login_and_domain_required
from requestlogger.models import RequestLog
from xformmanager.manager import readable_form, csv_dump

from releasemanager.forms import *

from rapidsms.webui.utils import render_to_response

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, HttpResponseRedirect
from django.contrib.auth.models import User
from django.http import *
from django.http import HttpResponse, HttpRequest
from django.http import HttpResponseRedirect, Http404, HttpResponseBadRequest
from django.core.urlresolvers import reverse
from django.forms.models import modelformset_factory

import mimetypes
import urllib
from xformmanager.xformdef import FormDef

from releasemanager.exceptions import *
import releasemanager.lib as lib


@login_and_domain_required
def projects(request, template_name="projects.html"):
    domain = request.user.selected_domain
    
    context = {'form' : BuildForm(), 'items': {}}
    resource_sets = {} ; release = {} ; unrelease = {}
        
    # wrestle w/ django's poor ORM, only to be subsequently crushed by its ridiculous templating system
    for rs in ResourceSet.objects.filter(domain=domain):
        r = Build.objects.filter(resource_set=rs).filter(is_release=True).order_by('-created_at')
        if len(r) > 0: release[rs.id] = r[0]
        
        r = Build.objects.filter(resource_set=rs).filter(is_release=False).order_by('-created_at')
        if len(r) > 0: unrelease[rs.id] = r[0]
        
        # don't include resource sets that haven't been used in a build yet
        if release.has_key(rs.id) or unrelease.has_key(rs.id):
            resource_sets[rs.id] = rs.name
            
    
    context['resource_sets'] = sorted(resource_sets.iteritems(), key=lambda (k,v): (v,k))    # sort by name
    context['release'] = release
    context['unrelease'] = unrelease
        
    # context['items'] = Build.objects.filter(is_release=True).filter(resource_set__domain=domain).order_by('-created_at')

    return render_to_response(request, template_name, context)
    
@login_and_domain_required
def jarjad_set_release(request, id, set_to):
    
    if not request.user.is_staff:
        return HttpResponseForbidden("Forbidden")
    
    if set_to == "true" or set_to == "false":
        Jarjad.objects.filter(id=id).update(is_release=(set_to == "true"))
    return HttpResponseRedirect(reverse('releasemanager.views.jarjad'))
    
@login_and_domain_required
def jarjad(request, template_name="jarjad.html"):
    
    if not request.user.is_staff:
        return HttpResponseForbidden("Forbidden")
        
    Jarjad.verify_all_files(delete_missing=True)
    
    context = {'form' : JarjadForm(), 'items': {}}
    context['items']['unreleased'] = Jarjad.objects.filter(is_release=False).order_by('-created_at')
    context['items']['released']   = Jarjad.objects.filter(is_release=True).order_by('-created_at')
    
    return render_to_response(request, template_name, context)


@login_and_domain_required
def make_release(request, id):
    Jarjad.objects.all().update(is_release=False)
    Jarjad.objects.filter(id=id).update(is_release=True)
    return HttpResponseRedirect(reverse('releasemanager.views.jarjad'))
    

@login_and_domain_required
def new_jarjad(request, template_name="jarjad.html"):
    '''save new Jad & Jar into the system'''
    if not request.user.is_staff:
        return HttpResponseForbidden("Forbidden")

    xml_mode = ('CCHQ-submitfromfile' in request.META['HTTP_USER_AGENT'])
        
    context = {}
    form = JarjadForm()    
    if request.method == 'POST':
        form = JarjadForm(request.POST, request.FILES)        
        if form.is_valid():
            try:                      
                jj = form.save(commit=False)

                jj.uploaded_by=request.user
                jj.description = urllib.unquote(jj.description)

                jj.save_file(request.FILES['jad_file_upload'])
                jj.save_file(request.FILES['jar_file_upload'])            

                jad = lib.jad_to_dict(open(jj.jad_file).read())
                jj.version = jad['MIDlet-Version']                

                jj.save()

                # _log_build_upload(request, newbuild)
                return HttpResponse("SUCCESS") if xml_mode else HttpResponseRedirect(reverse('releasemanager.views.jarjad'))
            except Exception, e:
                logging.error("Build upload error.", 
                              extra={'exception':e, 
                                     'request.POST': request.POST, 
                                     'request.FILES': request.FILES, 
                                     'form':form})
                context['errors'] = "Could not commit: " + str(e)
    
    context['form'] = form

    if xml_mode:
        return HttpResponseBadRequest("FAIL")
    else:
        return render_to_response(request, template_name, context)
    
    

@login_and_domain_required
def builds(request, template_name="builds.html"): 
    domain = request.user.selected_domain

    Build.verify_all_files(delete_missing=True)
    
    form = BuildForm()
    form.fields["resource_set"].queryset = ResourceSet.objects.filter(domain=domain)
    
    context = {'items': {}, 'form' : form}
        
    resource_set = request.GET['resource_set'] if request.GET.has_key('resource_set') else False
        
    if resource_set:
        context['resource_set'] = ResourceSet.objects.get(id=resource_set)
        
        context['items']['unreleased'] = Build.objects.filter(is_release=False).filter(resource_set=resource_set).filter(resource_set__domain=domain).order_by('-created_at')
        context['items']['released']   = Build.objects.filter(is_release=True).filter(resource_set=resource_set).filter(resource_set__domain=domain).order_by('-created_at')
    else:
        context['items']['unreleased'] = Build.objects.filter(is_release=False).filter(resource_set__domain=domain).order_by('-created_at')
        context['items']['released']   = Build.objects.filter(is_release=True).filter(resource_set__domain=domain).order_by('-created_at')

    return render_to_response(request, template_name, context)


@login_and_domain_required
def build_set_release(request, id, set_to):
    build = Build.objects.get(id=id)
    
    if set_to == "true":
        build.is_release=True
        lib.modify_jad(build.jad_file, {
                                        'CommCare-Release' : 'true', 
                                        'Released-on' : datetime.datetime.now().strftime("%Y-%b-%d %H:%M")
                                        })
    elif set_to == "false":
        build.is_release=False
        lib.modify_jad(build.jad_file, {
                                        'CommCare-Release' : 'false', 
                                        'Released-on' : ''
                                        })
    
    build.save()
    
    # rezip with the new file
    os.remove(build.zip_file)
    lib.create_zip(build.zip_file, build.jar_file, build.jad_file)
    
    return HttpResponseRedirect(reverse('releasemanager.views.builds'))


@login_and_domain_required
def new_build(request, template_name="builds.html"):
    context = {}
    buildform = BuildForm()    
    if request.method == 'POST':
        buildform = BuildForm(request.POST)
        if buildform.is_valid():
            b = buildform.save(commit=False)
            b.jar_file, b.jad_file, b.zip_file, form_errors = _create_build(request, b)
            b.save()
            
            lib.modify_jad(b.jad_file, {'Build-Number' : b.id })
            
            xsd_conversion_errors = [(form, errors) for form, errors in form_errors.items() \
                                     if isinstance(errors, XsdConversionError)]
            formdef_creation_errors = [(form, errors) for form, errors in form_errors.items() \
                                       if isinstance(errors, FormDefCreationError)]
            validation_errors = [(form, errors) for form, errors in form_errors.items() \
                                 if isinstance(errors, FormDef.FormDefError) \
                                    and errors.category == FormDef.FormDefError.ERROR]
            validation_warnings = [(form, errors) for form, errors in form_errors.items() \
                                 if isinstance(errors, FormDef.FormDefError) \
                                    and errors.category == FormDef.FormDefError.WARNING]
            registration_errors = {}
            if buildform.cleaned_data["register_forms"]:
                # FormDefErrors that are only warnings are allowable.  All other errors
                # are not.
                good_forms_list = [formname for formname, errors in form_errors.items()\
                                            if errors is None or \
                                                (isinstance(errors, FormDef.FormDefError) and \
                                                 errors.category == FormDef.FormDefError.WARNING)]
                
                registration_errors = lib.register_forms(b, good_forms_list)
            success_forms = [form for form, errors in form_errors.items() if errors is None]
            failed_registered = [form for form, errors in form_errors.items() if errors is not None]
            success_forms = [form for form in success_forms if form not in failed_registered]
            return render_to_response(request, "release_confirmation.html", 
                                      {"build": b,
                                       "success_forms": success_forms,
                                       "xsd_conversion_errors": xsd_conversion_errors,
                                       "formdef_creation_errors": formdef_creation_errors,
                                       "validation_errors": validation_errors,
                                       "validation_warnings": validation_warnings,
                                       "registration_errors": registration_errors
                                       })
            

    context['form'] = buildform
    return render_to_response(request, template_name, context)


@login_and_domain_required
def resource_sets(request, template_name="resource_sets.html"): 
    domain = request.user.selected_domain
    
    context = {'form' : ResourceSetForm(), 'items': {}}
    context['items']['unreleased'] = ResourceSet.objects.filter(is_release=False, domain=domain).order_by('-created_at')
    context['items']['released']   = ResourceSet.objects.filter(is_release=True, domain=domain).order_by('-created_at')

    return render_to_response(request, template_name, context)


@login_and_domain_required
def resource_set_set_release(request, id, set_to):
    if set_to == "true" or set_to == "false":
        ResourceSet.objects.filter(id=id).update(is_release=(set_to == "true"))
    return HttpResponseRedirect(reverse('releasemanager.views.resource_sets'))


@login_and_domain_required
def new_resource_set(request, template_name="resource_sets.html"):
    domain = request.user.selected_domain
    form = ResourceSetForm()    

    context = {'form' : form, 'items': {}}
    context['items']['unreleased'] = ResourceSet.objects.filter(is_release=False, domain=domain).order_by('-created_at')
    context['items']['released']   = ResourceSet.objects.filter(is_release=True, domain=domain).order_by('-created_at')

    if request.method == 'POST':
        form = ResourceSetForm(request.POST)
        if form.is_valid():
            r = form.save(commit=False)
            r.domain = request.user.selected_domain

            # resource_zip = lib.grab_from(r.url)
            # r.resource_dir = os.path.join(RESOURCE_PATH, r.name)
            # resources = lib.unzip(resource_zip, r.resource_dir)
            
            r.save()
            return HttpResponseRedirect(reverse('releasemanager.views.resource_sets'))

    context['form'] = form
    return render_to_response(request, template_name, context)


def _create_build(request, build):
    jar = build.jarjad.jar_file
    jad = build.jarjad.jad_file
    buildname = build.resource_set.name

    resources = lib.clone_from(build.resource_set.url)

    errors = lib.validate_resources(resources)

    for key, value in errors.items():
        if value: 
            logging.debug("Form validation error while realeasing build.  Form: %s, e: %s" % (key, value))

    ids = Build.objects.order_by('-id').filter(resource_set=build.resource_set)
    new_id = (1 + ids[0].id) if len(ids) > 0 else 1

    buildname_slug = re.sub('[\W_]+', '-', buildname)
    # str() to converts the names to ascii from unicode - zip has problems with unicode filenames
    new_path = os.path.join(BUILD_PATH, build.resource_set.domain.name, buildname_slug, str(new_id))
    if not os.path.isdir(new_path):
        os.makedirs(new_path)

    new_tmp_jar = lib.add_to_jar(jar, resources)    
    new_jar = str(os.path.join(new_path, "%s.jar" % buildname_slug))
    shutil.copy2(new_tmp_jar, new_jar)

    new_jad = str(os.path.join(new_path, "%s.jad" % buildname_slug))
    shutil.copy2(jad, new_jad)
    lib.modify_jad(new_jad, {
                                'MIDlet-Jar-Size' : os.path.getsize(new_jar), 
                                'MIDlet-Jar-URL' : os.path.basename(new_jar),
                            })

    # if "staging.commcarehq" in request.get_host().lower() or "localhost" in request.get_host().lower():
    lib.sign_jar(new_jar, new_jad)

    # create a zip
    new_zip = lib.create_zip(os.path.join(new_path, "%s.zip" % buildname_slug), new_jar, new_jad)

    # clean up tmp files
    os.remove(new_tmp_jar)

    return new_jar, new_jad, new_zip, errors
