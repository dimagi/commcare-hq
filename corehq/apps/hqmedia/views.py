import zipfile
import logging
import os
from django.utils.decorators import method_decorator
from django.views.generic import View
import magic
from StringIO import StringIO

from couchdbkit.exceptions import ResourceNotFound

from django.contrib.sites.models import Site
from django.http import HttpResponse, Http404, HttpResponseRedirect, HttpResponseServerError
from django.utils import simplejson
from django.views.decorators.http import require_POST
from django.shortcuts import render
from django.conf import settings

from corehq.apps.app_manager.decorators import safe_download
from corehq.apps.app_manager.views import require_can_edit_apps, set_file_download, ApplicationViewMixin
from corehq.apps.app_manager.models import get_app
from corehq.apps.domain.views import DomainViewMixin
from corehq.apps.hqmedia import utils
from corehq.apps.hqmedia.models import CommCareImage, CommCareAudio, CommCareMultimedia

X_PROGRESS_ERROR = 'Server Error: You must provide X-Progress-ID header or query param.'


def get_media_type(media_type):
    return {
        'CommCareImage': CommCareImage,
        'CommCareAudio': CommCareAudio,
    }[media_type]


def download_media(request, media_type, doc_id):
    try:
        media = get_media_type(media_type)
        try:
            try:
                media = media.get(doc_id)
            except Exception:
                logging.error("looks like %r.get(%r) failed" % (media, doc_id))
            data, content_type = media.get_display_file()
            response = HttpResponse(mimetype=content_type)
            response.write(data)
            return response
        except ResourceNotFound:
            raise Http404("No Media Found")
    except KeyError:
        raise Http404("unknown media type %s" % media_type)


@require_can_edit_apps
def search_for_media(request, domain, app_id):
    media_type = request.GET['t']
    if media_type == 'Image':
        files = CommCareImage.search(request.GET['q'])
    elif media_type == 'Audio':
        files = CommCareAudio.search(request.GET['q'])
    else:
        raise Http404()
    return HttpResponse(simplejson.dumps([
        {'url': i.url(),
         'licenses': [license.display_name for license in i.licenses],
         'tags': [tag for tags in i.tags.values() for tag in tags],
         'm_id': i._id} for i in files]))


@require_can_edit_apps
def choose_media(request, domain, app_id):
    # TODO: Add error handling
    app = get_app(domain, app_id)
    media_type = request.POST['media_type']
    media_id = request.POST['id']
    if media_type == 'Image':
        file = CommCareImage.get(media_id)
    elif media_type == 'Audio':
        file = CommCareImage.get(media_id)
    else:
        raise Http404()

    if file is None or not file.is_shared:
        return HttpResponse(simplejson.dumps({
            'match_found': False
        }))

    file.add_domain(domain)
    app.create_mapping(file, request.POST['path'])
    if media_type == 'Image':
        return HttpResponse(simplejson.dumps({
            'match_found': True,
            'image': {'m_id': file._id, 'url': file.url()},
            'file': True
        }))
    elif media_type == 'Audio':
        return HttpResponse(simplejson.dumps({'match_found': True, 'audio': {'m_id': file._id, 'url': file.url()}}))
    else:
        raise Http404()

@require_can_edit_apps
def media_urls(request, domain, app_id):
    # IS THIS USED?????
    # I rewrote it so it actually produces _something_, but is it useful???
    app = get_app(domain, app_id)
    multimedia = app.get_media_references()
    pathUrls = {}
    for section, types in multimedia['references'].items():
        for media_type, info in types.items():
            for m in info['maps']:
                if m.get('path'):
                    pathUrls[m['path']] = m

    return HttpResponse(simplejson.dumps(pathUrls))

@require_can_edit_apps
def media_map(request, domain, app_id):
    app = get_app(domain, app_id)
    multimedia = app.get_media_references()

    return render(request, "hqmedia/map.html", {
        "domain": domain,
        "app": app,
        "multimedia": multimedia,
    })

def media_from_path(request, domain, app_id, file_path):
    # Not sure what the intentions were for this. I didn't see it getting used anywhere.
    # Rewrote it to use new media refs.
    # Yedi, care to comment?
    app = get_app(domain, app_id)
    multimedia = app.get_media_references()

    for section, types in multimedia['references'].items():
        for media_type, info in types.items():
            for media_map in info['maps']:
                # [10:] is to remove the 'jr://file/'
                if media_map['path'][10:] == file_path and media_map.get('url'):
                    return HttpResponseRedirect(media_map['url'])

    raise Http404('No Media Found')

@require_can_edit_apps
def upload(request, domain, app_id):
    app = get_app(domain, app_id)
    DNS_name = "http://"+Site.objects.get(id = settings.SITE_ID).domain
    return render(request, "hqmedia/bulk_upload.html",
            {"domain": domain,
             "app": app,
             "DNS_name": DNS_name})

@require_POST
def uploaded(request, domain, app_id):
    app = get_app(domain, app_id)
    response = {}
    errors = []
    if request.POST.get('media_type', ''):
        specific_params = dict(request.POST)
    else:
        specific_params = {}

    replace_existing = request.POST.get('replace_existing', True)
    try:
        uploaded_file = request.FILES.get('Filedata')
        data = uploaded_file.file.read()
        mime = magic.Magic(mime=True)
        content_type = mime.from_buffer(data)
        uploaded_file.file.seek(0)
        matcher = utils.HQMediaMatcher(app, domain, request.user.username, specific_params)

        license = request.POST.get('license', "")
        author = request.POST.get('author', "")
        att_notes = request.POST.get('attribution-notes', "")

        if content_type in utils.ZIP_MIMETYPES:
            zip = zipfile.ZipFile(uploaded_file)
            bad_file = zip.testzip()
            if bad_file:
                raise Exception("Bad ZIP file.")
            matched_images, matched_audio, unknown_files, errors = matcher.match_zipped(zip,
                                                                                        replace_existing_media=replace_existing,
                                                                                        license=license,
                                                                                        author=author,
                                                                                        attribution_notes=att_notes)
            response = {"unknown": unknown_files,
                        "images": matched_images,
                        "audio": matched_audio,
                        "zip": True}
        else:
            if content_type in utils.IMAGE_MIMETYPES:
                file_type = "image"
            elif content_type in utils.AUDIO_MIMETYPES:
                file_type = "audio"
            else:
                raise Exception("Unsupported content type.")
            tags = [t.strip() for t in request.POST.get('tags', '').split(' ')]
            match_found, match_map, errors = matcher.match_file(uploaded_file,
                                                                replace_existing_media=replace_existing,
                                                                shared=request.POST.get('shared', False),
                                                                tags=tags,
                                                                license=license,
                                                                author=author,
                                                                attribution_notes=att_notes)
            response = {"match_found": match_found,
                        file_type: match_map,
                        "file": True}
    except Exception as e:
        errors.append(e.message)

    response['errors'] = errors
    return HttpResponse(simplejson.dumps(response))


class DownloadMultimediaZip(View, ApplicationViewMixin):
    """
        This is where the Multimedia for an application gets generated.
        Expects domain and app_id to be in its args, otherwise it's generally unhappy.
    """
    name = "download_multimedia_zip"

    @method_decorator(safe_download)
    def dispatch(self, request, *args, **kwargs):
        return super(DownloadMultimediaZip, self).dispatch(request, *args, **kwargs)

    def get(self, request, *args, **kwargs):
        errors = []
        temp = StringIO()
        media_zip = zipfile.ZipFile(temp, "a")
        self.app.remove_unused_mappings()
        if not self.app.multimedia_map:
            return HttpResponse("You have no multimedia to download.")
        print self.app.multimedia_map
        for path, media in self.app.get_media_objects():
            try:
                data, content_type = media.get_display_file()
                folder = path.replace(utils.MULTIMEDIA_PREFIX, "")
                print "FOLDER", folder
                if not isinstance(data, unicode):
                    media_zip.writestr(os.path.join(folder), data)
            except NameError as e:
                errors.append("%(path)s produced an ERROR: %(error)s" % {
                    'path': path,
                    'error': e,
                })
        media_zip.close()

        if errors:
            logging.error("Error downloading multimedia ZIP for domain %s and application %s." %
                          (self.domain, self.app_id))
            return HttpResponseServerError("Errors were encountered while "
                                           "retrieving media for this application.<br /> %s" % "<br />".join(errors))

        response = HttpResponse(mimetype="application/zip")
        set_file_download(response, 'commcare.zip')
        temp.seek(0)
        response.write(temp.read())
        return response

