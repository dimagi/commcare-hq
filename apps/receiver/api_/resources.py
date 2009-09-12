import os
import bz2
import sys
import logging
import settings
import traceback
import cStringIO
from django.http import HttpResponse, HttpResponseBadRequest
from django.core.servers.basehttp import FileWrapper
from receiver.models import Submission
from transformers.zip import TarCompressor
from hq.models import Domain
# TODO - pull out authentication stuff into some generic wrapper

# api/receiver/(?P<domain_id>\d+)
def get_submissions(request, domain_id=0):
    """ Takes a POST containing a tar of all MD5's
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
        return HttpResponseBadRequest( "Exception raised %s." % (e.message) )

def _get_submissions(request, domain_id=0):
    submissions = Submission.objects.all().order_by('checksum')

    # domain_id=0 is a temporary hack until we get server-server authentication
    # working properly
    if domain_id != 0:
        try:
            domain = Domain.objects.get(id=domain_id)
        except Domain.DoesNotExist:
            logging.error("Domain with id %s could not found." % domain_id)
            return HttpResponseBadRequest("Domain with id %s could not found." % domain_id)
        submissions.filter(domain=domain)
    if 'export_path' not in settings.RAPIDSMS_APPS['receiver']:
        logging.error("Please set 'export_path' in your cchq receiver settings.")
        return HttpResponseBadRequest("Please set 'export_path' in your cchq receiver settings.")
    export_dir = settings.RAPIDSMS_APPS['receiver']['export_path']
    if 'file' in request.FILES:
        try:
            md5_string = bz2.decompress(request.FILES['file'].read())
        except Exception, e:
            logging.error("Poorly formatted tar file. Expecting a tar of md5 values.")
            return HttpResponseBadRequest("Poorly formatted tar file. Expecting a tar of md5 values.")
        md5_stream = cStringIO.StringIO(md5_string)
        stack_received = []
        
        line = md5_stream.readline()
        while len(line)>0:
            # assume we receive an ordered list of MD5
            stack_received.append( line.strip() )
            line = md5_stream.readline()
        
        # compare the list of received MD5's with the local mD5
        counter_received = 0
        counter_local = 0
        results = []
        stack_local = Submission.objects.all().order_by('checksum').values_list('checksum', flat=True)
        while True:
            if counter_received == len(stack_received):
                results.extend(stack_local[counter_local:])
                break
            if counter_local == len(stack_local):
                # Reached the end of the list of local submissions before reaching
                # the end of received mD5s. This should really never happen. 
                # But might, if you were syncing with two different cchq servers.
                logging.warn("Local submission count less than received submission count!")
                break
            if stack_received[counter_received] == stack_local[counter_local]:
                counter_received = counter_received + 1
                counter_local = counter_local + 1
            elif stack_received[counter_received] > stack_local[counter_local]:
                # found an entry in local which is not in received
                results.append( stack_local[counter_local] )
                counter_local = counter_local + 1
            else:
                # found an entry in received which is not in local
                # skip it
                logging.error("Skipping unrecognized received MD5!")
                counter_received = counter_received + 1
        # this could get really large.... O_O
        submissions = Submission.objects.filter(checksum__in=results).order_by("checksum")
    
    compressor = TarCompressor()
    export_path = os.path.join( export_dir, "commcarehq-submissions.tar")
    compressor.open(name=export_path)
    file_added = False
    for submission in submissions:
        # use StringIO for now, since tarfile requires a stream object
        # Revisit if xforms get super long
        try:
            string = cStringIO.StringIO( submission.export() )
        except Submission.DoesNotExist:
            logging.error("%s could not be found. Data export failed." \
                          % submission.raw_post)
            continue
        file_added = True
        size = string.tell()
        string.seek(0)
        compressor.add_stream(string, size, name=os.path.basename(submission.raw_post) )    
    compressor.close()
    if not file_added:
        logging.info("No submissions could be found.")
        return HttpResponse("No submissions could be found.")
    response = HttpResponse()
    response['Content-Length'] = os.path.getsize(export_path)
    fin = open(export_path, 'rb')
    wrapper = FileWrapper(fin)
    response = HttpResponse(wrapper, content_type='application/tar')
    response['Content-Disposition'] = 'attachment; filename=commcarehq-submissions.tar'
    return response

""" 
We do not need the following parameters for now.
But we might as some point, so I'll keep 'em around for a bit.


Exports complete submission data (including headers) to tar format
(which is more unicode-friendly than zip). This is fairly duplicated with the
'create' function above, but we keep it around in case anyone wants to request
submissions by id or date or whatever

TODO - make this mutipart/byte-friendly
""
    
    submissions = Submission.objects.all()
    
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
    if request.REQUEST.has_key('received_count'):
        # when the satellite server specifies how many it has received
        # the master server responds with all the missing submissions
        received_count = int(request.GET['received_count'])
        count = submissions.count()
        missing_count = count - received_count
        submissions = submissions[0:missing_count]
    if 'export_path' not in settings.RAPIDSMS_APPS['receiver']:
        return HttpResponseBadRequest("Please set 'export_path' " + \
                                      "in your cchq receiver settings.")


"""
