import os
import tarfile
import StringIO
import logging
import settings
from datetime import datetime
from django.http import HttpResponse, HttpResponseBadRequest
from django.core.servers.basehttp import FileWrapper
from django_rest_interface.resource import Resource
from receiver.models import Submission
from transformers.zip import TarCompressor
from hq.models import Domain

# TODO - pull out authentication stuff into some generic wrapper

# api/receiver/(?P<domain_id>\d+)
class Submissions(Resource):
    def read(self, request, domain_id=0):
        """ Exports complete submission data (including headers) to tar format
        (which is more unicode-friendly than zip)
        
        TODO - make this mutipart/byte-friendly
        """
        
        submissions = Submission.objects.all().order_by('id')
        # domain_id=0 is a temporary hack until we get server-server authentication
        # working properly
        if domain_id != 0:
            try:
                domain = Domain.objects.get(id=domain_id)
            except Domain.DoesNotExist:
                return HttpResponseBadRequest("Domain with id %s could not found." % domain_id)
            submissions = Submission.objects.filter(domain=domain)
        if request.REQUEST.has_key('start-id'):
            submissions = submissions.filter(id__gte=request.GET['start-id'])
        if request.REQUEST.has_key('end-id'):
            submissions = submissions.filter(id__lte=request.GET['end-id'])
        if request.REQUEST.has_key('start-date'):
            date = datetime.strptime(request.GET['start-date'],"%Y-%m-%d")
            submissions = submissions.filter(submit_time__gte=date)
        if request.REQUEST.has_key('end-date'):
            date = datetime.strptime(request.GET['end-date'],"%Y-%m-%d")
            submissions = submissions.filter(submit_time__lte=date)
        export_path = os.path.join( settings.RAPIDSMS_APPS['receiver']['export_path'], \
                                    "commcarehq-submissions.tar")
        export_file = open( export_path, mode="w+b")
        compressor = TarCompressor()
        compressor.open(export_file)
        fileAdded = False
        for submission in submissions:
            # use StringIO for now, since tarfile requires a stream object
            # Revisit if xforms get super long
            string = StringIO.StringIO()
            try:
                string.write( unicode(submission.export()) )
            except Submission.DoesNotExist:
                logging.error("%s could not be found. Data export failed." \
                              % submission.raw_post)
                continue
            fileAdded = True
            size = string.tell()
            string.seek(0)
            compressor.add_stream(string, size, name=os.path.basename(submission.raw_post) )
        compressor.close()
        if not fileAdded: return HttpResponseBadRequest("No submissions could be found.")
        response = HttpResponse()
        wrapper = FileWrapper(export_file)
        response = HttpResponse(wrapper, content_type='application/tar')
        response['Content-Disposition'] = 'attachment; filename=commcarehq-submissions.tar'
        response['Content-Length'] = export_file.tell()
        # this seek is required for 'response' to work
        export_file.seek(0)
        return response





