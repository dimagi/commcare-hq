import uuid
from django.conf import settings
from couchdbkit.exceptions import ResourceNotFound
from django.contrib.sites.models import Site
from django.http import HttpResponse, HttpResponseServerError, Http404
from django.utils import simplejson
from corehq.apps.hqmedia import upload
from corehq.apps.hqmedia.forms import HQMediaZipUploadForm, HQMediaFileUploadForm
from corehq.apps.hqmedia.models import *
from corehq.apps.users.decorators import require_permission
from corehq.apps.app_manager.models import Application, get_app
from dimagi.utils.web import render_to_response

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


@require_permission('edit-apps')
def upload(request, domain, app_id):
    kind='zip'
    app = get_app(domain, app_id)
    DNS_name = "http://"+Site.objects.get(id = settings.SITE_ID).domain
    return render_to_response(request, "hqmedia/upload_zip.html",
            {"domain": domain,
             "app": app,
             "DNS_name": DNS_name})

def uploaded(request, domain, app_id):
    print "uploaded files"
    return HttpResponse(simplejson.dumps({}))
