import uuid
from datetime import datetime
from django.contrib.auth.decorators import login_required
from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect, Http404, HttpResponse
from django.core.cache import cache
import logging
from django.shortcuts import render_to_response
from django.template.context import RequestContext
from soil.tasks import demo_sleep
import json
from soil.heartbeat import get_file_heartbeat, get_cache_heartbeat,\
    last_heartbeat

def _parse_date(string):
    if isinstance(string, basestring):
        return datetime.strptime(string, "%Y-%m-%d").date()
    else:
        return string


@login_required
def demo(request):
    download_id = uuid.uuid4().hex
    howlong = int(request.GET.get('secs', 5))
    demo_sleep.delay(download_id, howlong)
    return HttpResponseRedirect(reverse('retrieve_download', kwargs={'download_id': download_id}))

@login_required
def heartbeat_status(request):
    return HttpResponse(json.dumps({"last_timestamp": str(last_heartbeat()),
                                    "last_from_file": get_file_heartbeat(),
                                    "last_from_cache": get_cache_heartbeat()}))
    

@login_required
def ajax_job_poll(request, download_id, template="soil/partials/dl_status.html"):
    download_data = cache.get(download_id, None)
    if download_data == None:
        is_ready = False
    else:
        is_ready=True
    context = RequestContext(request)
    context['is_ready'] = is_ready
    context['download_id'] = download_id
    return render_to_response(template, context_instance=context)


@login_required
def retrieve_download(request, download_id, template="soil/file_download.html"):
    """
    Retrieve a download that's waiting to be generated. If it is the get_file, 
    then download it, else, let the ajax on the page poll.
    """
    context = RequestContext(request)
    context['download_id'] = download_id
    do_download = request.GET.has_key('get_file')
    if do_download:
        download = cache.get(download_id, None)
        if download == None:
            logging.error("Download file request for expired/nonexistent file requested")
            raise Http404
        else:
            return download.toHttpResponse()

    return render_to_response(template, context_instance=context)



