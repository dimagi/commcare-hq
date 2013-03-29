import zipfile
import logging
import os
from django.contrib.auth.decorators import login_required
import magic
import json
from django.core.urlresolvers import reverse
from django.core.cache import cache
from django.template.loader import render_to_string
from django.utils.decorators import method_decorator
from django.views.generic import View, TemplateView
from StringIO import StringIO

from couchdbkit.exceptions import ResourceNotFound

from django.http import HttpResponse, Http404, HttpResponseRedirect, HttpResponseServerError, HttpResponseBadRequest

from django.views.decorators.http import require_POST
from django.shortcuts import render
from django.conf import settings

from corehq.apps.app_manager.decorators import safe_download
from corehq.apps.app_manager.views import require_can_edit_apps, set_file_download, ApplicationViewMixin
from corehq.apps.app_manager.models import get_app
from corehq.apps.hqmedia import utils
from corehq.apps.hqmedia.models import CommCareImage, CommCareAudio, CommCareMultimedia, MULTIMEDIA_PREFIX
from corehq.apps.hqmedia.tasks import process_bulk_upload_zip

from dimagi.utils import make_uuid
from dimagi.utils.decorators.memoized import memoized

DEFAULT_EXPIRY = 60 * 60  # one hour


class BaseMultimediaView(ApplicationViewMixin, View):

    @method_decorator(require_can_edit_apps)
    def dispatch(self, request, *args, **kwargs):
        return super(BaseMultimediaView, self).dispatch(request, *args, **kwargs)


class BaseMultimediaTemplateView(BaseMultimediaView, TemplateView):
    """
        The base view for all the multimedia templates.
    """

    @property
    def page_context(self):
        return {}

    def get_context_data(self, **kwargs):
        context = {
            "domain": self.domain,
            "app": self.app,
        }
        context.update(self.page_context)
        return context

    def render_to_response(self, context, **response_kwargs):
        return render(self.request, self.template_name, context)


@require_can_edit_apps
def search_for_media(request, domain, app_id):
    media_type = request.GET['t']
    if media_type == 'Image':
        files = CommCareImage.search(request.GET['q'])
    elif media_type == 'Audio':
        files = CommCareAudio.search(request.GET['q'])
    else:
        raise Http404()
    return HttpResponse(json.dumps([
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
        return HttpResponse(json.dumps({
            'match_found': False
        }))

    file.add_domain(domain)
    app.create_mapping(file, request.POST['path'])
    if media_type == 'Image':
        return HttpResponse(json.dumps({
            'match_found': True,
            'image': {'m_id': file._id, 'url': file.url()},
            'file': True
        }))
    elif media_type == 'Audio':
        return HttpResponse(json.dumps({'match_found': True, 'audio': {'m_id': file._id, 'url': file.url()}}))
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

    return HttpResponse(json.dumps(pathUrls))


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


class BaseUploaderMultimediaView(BaseMultimediaTemplateView):
    upload_multiple_files = True
    queue_template_name = None
    status_template_name = None
    details_template_name = None
    errors_template_name = None

    @property
    def page_context(self):
        return {
            'uploader': {
                'file_filters': self.supported_files,
                'destination': self.upload_url,
                'processing_url': self.processing_url,
                'multi_file': self.upload_multiple_files,
                'queue_template': render_to_string(self.queue_template_name, {}),
                'status_template': render_to_string(self.status_template_name, {}),
                'details_template': render_to_string(self.details_template_name, {}),
                'errors_template': render_to_string(self.errors_template_name, {}),
                'licensing_params': self.licensing_params,
                'upload_params': self.upload_params,
            },
        }

    @property
    def supported_files(self):
        """
            A list of dicts of accepted file extensions by the YUI Uploader widget.
        """
        return [
            {
                'description': 'Zip',
                'extensions': '*.zip',
                },
            ]

    @property
    def licensing_params(self):
        return ['shared', 'license', 'author', 'attribution-notes']

    @property
    def upload_params(self):
        return {
            'replace_existing': False,
        }

    @property
    def upload_url(self):
        """
            The URL to post the file upload data to.
        """
        raise NotImplementedError("You must specify an upload url.")

    @property
    def processing_url(self):
        return reverse(MultimediaUploadStatus.name)


class BulkUploadMultimediaView(BaseUploaderMultimediaView):
    name = "hqmedia_bulk_upload"
    template_name = "hqmedia/bulk_upload.html"

    queue_template_name = "hqmedia/uploader/queue_multi.html"
    status_template_name = "hqmedia/uploader/status_multi.html"
    details_template_name = "hqmedia/uploader/details_multi.html"
    errors_template_name = "hqmedia/uploader/errors_multi.html"

    @property
    def upload_url(self):
        return reverse(ProcessBulkUploadView.name, args=[self.domain, self.app_id])


class BadMediaFileException(Exception):
    pass


class BaseProcessUploadedView(BaseMultimediaView):

    @property
    @memoized
    def replace_existing(self):
        return self.request.POST.get('replace_existing') == 'true'

    @property
    @memoized
    def share_media(self):
        return self.request.POST.get('shared') == 't'

    @property
    @memoized
    def license_used(self):
        return self.request.POST.get('license', '')

    @property
    @memoized
    def author(self):
        return self.request.POST.get('author', '')

    @property
    @memoized
    def attribution_notes(self):
        return self.request.POST.get('attribution-notes', '')

    @property
    @memoized
    def uploaded_file(self):
        return self.request.FILES.get('Filedata')

    @property
    @memoized
    def mime_type(self):
        try:
            data = self.uploaded_file.file.read()
            mime = magic.Magic(mime=True)
            return mime.from_buffer(data)
        except Exception as e:
            return BadMediaFileException("There was an error fetching the MIME type of your file. Error: %s" % e)

    def get(self, request, *args, **kwargs):
        return HttpResponseBadRequest("You may only post to this URL.")

    def post(self, request, *args, **kwargs):
        self.errors = []
        try:
            self.validate_file()
        except BadMediaFileException as e:
            self.errors.append(e.message)
        upload_response = self.process_upload()
        response = {
            'errors': self.errors,
        }
        response.update(upload_response)
        return HttpResponse(json.dumps(response))

    def validate_file(self):
        if not self.mime_type in self.valid_mime_types():
            raise BadMediaFileException("You uploaded a file with an invalid MIME type.")

    def process_upload(self):
        raise NotImplementedError("You definitely need to implement this guy.")

    @classmethod
    def valid_mime_types(cls):
        raise NotImplementedError("You must provide valid MIME Types so the validator can function")


class ProcessBulkUploadView(BaseProcessUploadedView):
    name = "hqmedia_uploader_bulk"

    @property
    @memoized
    def uploaded_zip(self):
        try:
            self.uploaded_file.file.seek(0)
            return zipfile.ZipFile(self.uploaded_file)
        except Exception as e:
            raise BadMediaFileException("There was an issue processing the zip file you provided. Error: %s" % e)

    def validate_file(self):
        super(ProcessBulkUploadView, self).validate_file()
        if not self.uploaded_zip:
            raise BadMediaFileException("There is no ZIP file.")
        if self.uploaded_zip.testzip():
            raise BadMediaFileException("The ZIP file provided was bad.")

    def process_upload(self):
        processing_id = make_uuid()
        self.uploaded_file.file.seek(0)
        # borrowed from a number of places. ex: http://code.activestate.com/recipes/273844-minimal-http-upload-cgi/
        saved_file = file(self.get_save_path(processing_id), 'wb')
        while 1:
            chunk = self.uploaded_file.file.read(100000)
            if not chunk:
                break
            saved_file.write(chunk)
        saved_file.close()
        status = {
            'in_celery': False,
            'complete': False,
            'progress': 0,
            'errors': [],
            'type': 'zip',
            'processing_id': processing_id,
        }
        cache.set(self.get_cache_key(processing_id), status)
        process_bulk_upload_zip.delay(processing_id, self.domain, self.app_id,
                                      username=self.request.couch_user.username if self.request.couch_user else None,
                                      share_media=self.share_media,
                                      license_name=self.license_used, author=self.author,
                                      attribution_notes=self.attribution_notes, replace_existing=self.replace_existing)
        return status

    @classmethod
    def valid_mime_types(cls):
        return [
            'application/zip',
            'application/x-zip',
            'application/octet-stream',
            'application/x-zip-compressed',
        ]

    @classmethod
    def get_bulk_upload_location(cls):
        try:
            return settings.MULTIMEDIA_BULK_UPLOAD_LOCATION
        except AttributeError:
            raise NotImplementedError("You need to specify a bulk upload location (MULTIMEDIA_BULK_UPLOAD_LOCATION) "
                                      "in your localsettings to use this feature")

    @classmethod
    def get_save_path(cls, processing_id):
        return os.path.join(cls.get_bulk_upload_location(), "%s.zip" % processing_id)

    @classmethod
    def get_cache_key(cls, processing_id):
        return "MMBULK_%s" % processing_id


class CheckOnProcessingFile(BaseMultimediaView):
    name = "hqmedia_check_processing"

    def get(self, request, *args, **kwargs):
        return HttpResponse("workin on it")


@require_POST
def uploaded(request, domain, app_id):
    # todo move this over to something similar to what bulk upload does
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

        if not content_type in utils.ZIP_MIMETYPES:
            # zip files are no longer handled here todo clean this up too
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
    return HttpResponse(json.dumps(response))


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
        for path, media in self.app.get_media_objects():
            try:
                data, content_type = media.get_display_file()
                folder = path.replace(MULTIMEDIA_PREFIX, "")
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


class MultimediaUploadStatus(View):
    name = "hqmedia_upload_status"

    @property
    @memoized
    def processing_id(self):
        return self.request.POST.get('processing_id')

    @method_decorator(login_required)
    def dispatch(self, request, *args, **kwargs):
        return super(MultimediaUploadStatus, self).dispatch(request, *args, **kwargs)

    def get(self, request, *args, **kwargs):
        return HttpResponseBadRequest("Please post to this.")

    def post(self, request, *args, **kwargs):
        if not self.processing_id:
            return HttpResponseBadRequest("A processing_id is required.")
        cache_key = ProcessBulkUploadView.get_cache_key(self.processing_id)
        progress_info = cache.get(cache_key)
        return HttpResponse(json.dumps(progress_info))


class ViewMultimediaFile(View):
    name = "hqmedia_download"

    @property
    @memoized
    def media_class(self):
        media_type = self.kwargs.get('media_type')
        try:
            return CommCareMultimedia.get_doc_class(media_type)
        except KeyError:
            raise Http404("Could not find media of that type.")

    @property
    @memoized
    def doc_id(self):
        return self.kwargs.get('doc_id')

    @property
    @memoized
    def multimedia(self):
        try:
            return self.media_class.get(self.doc_id)
        except ResourceNotFound:
            raise Http404("Media not found.")

    @property
    @memoized
    def thumb(self):
        thumb = self.request.GET.get('thumb')
        try:
            return int(thumb), int(thumb)
        except Exception:
            return None

    def get(self, request, *args, **kwargs):
        data, content_type = self.multimedia.get_display_file()
        if self.media_class == CommCareImage:
            data = self.resize_image(data)
        response = HttpResponse(mimetype=content_type)
        response.write(data)
        return response

    def resize_image(self, data):
        if self.thumb:
            return self.multimedia.get_thumbnail_data(data, self.thumb)
        return data
