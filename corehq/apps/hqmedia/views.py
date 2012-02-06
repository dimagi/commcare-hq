from couchdbkit.exceptions import ResourceNotFound
from django.http import HttpResponse, HttpResponseServerError
from django.utils import simplejson
from corehq.apps.hqmedia import upload
from corehq.apps.hqmedia.models import *

X_PROGRESS_ERROR = 'Server Error: You must provide X-Progress-ID header or query param.'

def download_media(request, domain, media_type, doc_id):
    # TODO limit access to relevant domains
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
    cache_handler = upload.HQMediaUploadCacheHandler.handler_from_request(request, domain)
    if cache_handler:
        cache_handler.sync()
        return HttpResponse(simplejson.dumps(cache_handler.data))
    else:
        return HttpResponseServerError(X_PROGRESS_ERROR)

def check_upload_success(request, domain):
    """
    Return JSON object with information about files that failed to sync with couch after
    a zip upload---can only by accessed once, and later returns an empty JSON object.
    """
    cache_handler = upload.HQMediaUploadSuccessCacheHandler.handler_from_request(request, domain)
    if cache_handler:
        cache_handler.sync()
        cached_data = cache_handler.data
        cache_handler.delete()
        return HttpResponse(simplejson.dumps(cached_data))
    else:
        return HttpResponseServerError(X_PROGRESS_ERROR)