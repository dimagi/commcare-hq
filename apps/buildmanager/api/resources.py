import os
import bz2
import sys
import logging
import traceback
import cStringIO
import tempfile

from django.conf import settings
from django.http import HttpResponse, HttpResponseBadRequest
from django.core.servers.basehttp import FileWrapper
from django.core import serializers

from buildmanager.models import Project, ProjectBuild
from transformers.zip import TarCompressor, build_tarfile
from hq.models import Domain
from django_rest_interface import util


def get_builds(request):
    """Takes a POST containing a tar of all MD5's
       and returns a tar of all missing submissions
    
       Heh, this is explicitly against good REST methodology 
       We leave this inside the django-rest 'Resource' so we can
       use their authentication tools
    """
    try:
        return _get_builds(request)
    except Exception, e:
        type, value, tb = sys.exc_info()
        logging.error( "EXCEPTION raised: %s" % (str(e)) )
        logging.error( "TRACEBACK:\n%s" % ('\n'.join(traceback.format_tb(tb))) )
        raise
        return HttpResponseBadRequest( "Exception raised %s." % e )

def get_builds_for_domain(request, domain_id):
    """Takes a POST containing a tar of all MD5's
       and returns a tar of all missing submissions
    
       Heh, this is explicitly against good REST methodology 
       We leave this inside the django-rest 'Resource' so we can
       use their authentication tools
    """
    try:
        return _get_submissions(request, domain_id)
    except Exception, e:
        type, value, tb = sys.exc_info()
        logging.error( "EXCEPTION raised: %s" % (str(e)) )
        logging.error( "TRACEBACK:\n%s" % ('\n'.join(traceback.format_tb(tb))) )
        return HttpResponseBadRequest( "Exception raised %s." % e )

def _get_builds(request, domain_id=None):
    
    projects = Project.objects.all()
    if domain_id:
        # filter on domain, if it's set
        try:
            domain = Domain.objects.get(id=domain_id)
        except Domain.DoesNotExist:
            logging.error("Domain with id %s could not found." % domain_id)
            return HttpResponseBadRequest("Domain with id %s could not found." % domain_id)
        projects = projects.filter(domain=domain)
    
    if 'export_path' not in settings.RAPIDSMS_APPS['buildmanager']:
        logging.error("Please set 'export_path' in your hq buildmanager settings.")
        return HttpResponseBadRequest("Please set 'export_path' in your hq buildmanager settings.")
    export_dir = settings.RAPIDSMS_APPS['buildmanager']['export_path']
    
    # For now this is RESTful, and de-facto returns all projects and builds.  
    # At some point we may require this to take in a list of guids or 
    # checksums much like the receiver does.
    
    if projects.count() == 0:
        logging.info("No projects could be found.")
        return HttpResponse("No projects could be found.")
    
    builds = ProjectBuild.objects.filter(project__in=projects)
    if builds.count() == 0:
        logging.info("No builds could be found.")
        return HttpResponse("No builds could be found.")
    
    compressor = TarCompressor()
    export_path = os.path.join( export_dir, "commcarehq-builds.tar")
    compressor.open(name=export_path)
    # add the root project summaries to the compressor
    _add_to_compressor(compressor, _get_project_summary(projects), "projects.json")
    tars = []
    for build in builds:
        try:
            summary_tar = _get_build_summary(build)
            tars.append(summary_tar)
            compressor.add_file(summary_tar.name)
        except Exception, e:
            logging.error("Unable to export build: %s.  Error is %s." % (build, e))
            raise
        
    compressor.close()
    response = HttpResponse()
    response['Content-Length'] = os.path.getsize(export_path)
    fin = open(export_path, 'rb')
    wrapper = FileWrapper(fin)
    response = HttpResponse(wrapper, content_type='application/tar')
    response['Content-Disposition'] = 'attachment; filename=commcarehq-builds.tar'
    return response


def _get_project_summary(projects):
    """Returns a single json string with the summary of the projects"""
    return serializers.serialize('json', projects)

def _get_build_summary(build):
    """Package a build's metadata with its jad and jar and return it
       as a tarball"""
    temp_tar_path = tempfile.TemporaryFile().name
    temp_json_path = os.path.join(tempfile.tempdir, "build%s.json" % build.id)
    json_file = open(temp_json_path, "wb")
    json_file.write(serializers.serialize('json', [build]))
    json_file.close()
    tarball = build_tarfile([json_file.name, build.jar_file, build.jad_file], temp_tar_path)
    tarball.close()
    return tarball

def _get_build_filename(build):
    """A unique but semi-readable filename to reference the build"""
    return "%s-%s-%s.build" % (build.project.domain.name, build.project.name, build.id)

def _add_to_compressor(compressor, data, filename):
    """Add some data to the (assumed to be open) tar archive"""
    compressor.add_stream(cStringIO.StringIO( data ), len(data), name=filename)
    
def _add_stream_to_compressor(compressor, data, length, filename):
    """Add some data to the (assumed to be open) tar archive"""
    compressor.add_stream(data, length, name=filename)
    
    