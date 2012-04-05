import uuid
import magic
from django.conf import settings
from couchdbkit.exceptions import ResourceNotFound
from django.contrib.sites.models import Site
from django.http import HttpResponse, HttpResponseServerError, Http404
from django.utils import simplejson
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
import zipfile
from corehq.apps.hqmedia import upload, utils
from corehq.apps.hqmedia.forms import HQMediaZipUploadForm, HQMediaFileUploadForm
from corehq.apps.hqmedia.models import *
from corehq.apps.users.decorators import require_permission
from corehq.apps.app_manager.models import Application, get_app
from dimagi.utils.web import render_to_response

X_PROGRESS_ERROR = 'Server Error: You must provide X-Progress-ID header or query param.'

def download_media(request, media_type, doc_id):
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


@require_permission('edit-apps')
def upload(request, domain, app_id):
    app = get_app(domain, app_id)
    DNS_name = "http://"+Site.objects.get(id = settings.SITE_ID).domain
    return render_to_response(request, "hqmedia/bulk_upload.html",
            {"domain": domain,
             "app": app,
             "DNS_name": DNS_name})

@require_POST
def uploaded(request, domain, app_id):
    app = get_app(domain, app_id)
    try:
        uploaded_file = request.FILES.get('Filedata')
        data = uploaded_file.file.read()
        mime = magic.Magic(mime=True)
        content_type = mime.from_buffer(data)
        uploaded_file.file.seek(0)
        matcher = utils.HQMediaMatcher(app, domain, request.user.username)

        if content_type in utils.ZIP_MIMETYPES:
            zip = zipfile.ZipFile(uploaded_file)
            bad_file = zip.testzip()
            # TODO: hadnle bad zipfile

            matched_images, matched_audio, unknown_files = matcher.match_zipped(zip)
            return HttpResponse(simplejson.dumps({"unknown": unknown_files,
                                                  "images": matched_images,
                                                  "audio": matched_audio,
                                                  "zip": True}))
        if content_type in utils.IMAGE_MIMETYPES:
            file_type = "image"
        elif content_type in utils.AUDIO_MIMETYPES:
            file_type = "audio"
        else:
            raise Exception("Unsupported content type.")

        match_found, match_map = matcher.match_file(uploaded_file)
        return HttpResponse(simplejson.dumps({"match_found": match_found,
                                                  file_type: match_map,
                                                  "file": True}))

    except Exception as e:
        print e
        return HttpResponse(simplejson.dumps({"error": e}))
