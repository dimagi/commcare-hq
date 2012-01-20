from couchdbkit.exceptions import ResourceNotFound
from django.http import HttpResponse, HttpResponseServerError
from corehq.apps.hqmedia.models import *
from django.core.cache import cache

def download_media(request, domain, media_type, doc_id):
    try:
        media = eval(media_type)
        try:
            media = media.get(doc_id)
            data, content_type = media.get_display_file()
            response = HttpResponse(mimetype=content_type)
            response.write(data)
            return response
        except ResourceNotFound:
            pass
    except NameError:
        pass
    return HttpResponseServerError("No Media Found")

def check_upload_progress(request, domain):
    """
    Return JSON object with information about the progress of an upload.
    """
    progress_id = ''
    if 'X-Progress-ID' in request.GET:
        progress_id = request.GET['X-Progress-ID']
    elif 'X-Progress-ID' in request.META:
        progress_id = request.META['X-Progress-ID']
    if progress_id:
        from django.utils import simplejson
        cache_key = "%s_%s" % (request.META['REMOTE_ADDR'], progress_id)
        data = cache.get(cache_key)
        return HttpResponse(simplejson.dumps(data))
    else:
        return HttpResponseServerError('Server Error: You must provide X-Progress-ID header or query param.')