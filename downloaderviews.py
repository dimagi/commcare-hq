import uuid
from datetime import datetime, timedelta
from django.contrib.auth.decorators import login_required
from django.core.servers.basehttp import FileWrapper
from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect, HttpResponse, Http404
from django.core.cache import cache
import logging
from django.shortcuts import render_to_response
from django.template.context import RequestContext
from django.utils import simplejson

def _parse_date(string):
    if isinstance(string, basestring):
        return datetime.strptime(string, "%Y-%m-%d").date()
    else:
        return string


@login_required
def ajax_job_poll(request, download_id, template="downloader/partials/dl_status.html"):
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
def retrieve_download(request, download_id, template="downloader/file_download.html"):
    """Retrieve a download that's waiting to be generated. If it is the get_file, then download it, else, let the ajax on the page poll.
    """
    context = RequestContext(request)
    context['download_id'] = download_id
    do_download = request.GET.has_key('get_file')
    if do_download:
        download_data = cache.get(download_id, None)
        if download_data == None:
            logging.error("Download file request for expired/nonexistent file requested")
            raise Http404
        else:
            download_json = simplejson.loads(download_data)

            if download_json['location'] == None:
                #there's no data, likely an error
                response = HttpResponse(mimetype=download_json['mimetype'])
                if download_json.has_key('message'):
                    response.write(download_json['message'])
                else:
                    response.write("No data")
                return response

            f = file(download_json['location'], 'rb')
            wrapper = FileWrapper(f)
            response = HttpResponse(wrapper, mimetype=download_json['mimetype'])
            response['Transfer-Encoding'] = 'chunked'
            response['Content-Disposition'] = download_json['Content-Disposition']
            return response
    return render_to_response(template, context_instance=context)



