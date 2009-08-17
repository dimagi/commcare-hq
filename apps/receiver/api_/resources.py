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
from hq.models import Domain

# TODO - pull out authentication stuff into some generic wrapper

# api/receiver/(?P<domain_id>\d+)
class Submissions(Resource):
    def read(self, request, domain_id):
        """ Exports complete submission data (including headers) to tar format
        
        TODO - make this mutipart/byte-friendly
        """
        try:
            domain = Domain.objects.get(id=domain_id)
        except Domain.DoesNotExist:
            return HttpResponseBadRequest("Domain with id %s could not found." % domain_id)
        submissions = Submission.objects.filter(domain=domain).order_by('id')
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
        tar = tarfile.open(fileobj=export_file, mode="w")
        for submission in submissions:
            # use StringIO for now. Revisit if xforms get super long
            string = StringIO.StringIO()
            try:
                string.write( submission.export() )
            except Submission.DoesNotExist:
                logging.error("%s could not be found. Data export failed." \
                              % submission.raw_post)
                continue
            string.seek(0)
            tar_info = tarfile.TarInfo(name=os.path.basename(submission.raw_post) )
            tar_info.size = len(string.buf)
            tar.addfile(tar_info, fileobj=string)
        tar.close()
        response = HttpResponse()
        wrapper = FileWrapper(export_file)
        response = HttpResponse(wrapper, content_type='application/tar')
        response['Content-Disposition'] = 'attachment; filename=commcarehq-submissions.tar'
        response['Content-Length'] = export_file.tell()
        # this seek is required for 'response' to work
        export_file.seek(0)
        return response





