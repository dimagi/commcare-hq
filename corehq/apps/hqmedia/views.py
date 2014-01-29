from StringIO import StringIO
from mimetypes import guess_all_extensions, guess_type
import tempfile
import zipfile
import logging
import os
from django.contrib.auth.decorators import login_required
from django.core.servers.basehttp import FileWrapper
import json
from django.core.urlresolvers import reverse
from django.utils.decorators import method_decorator
from django.views.generic import View, TemplateView

from couchdbkit.exceptions import ResourceNotFound

from django.http import HttpResponse, Http404, HttpResponseRedirect, HttpResponseServerError, HttpResponseBadRequest

from django.shortcuts import render

from corehq.apps.app_manager.decorators import safe_download
from corehq.apps.app_manager.views import require_can_edit_apps, set_file_download, ApplicationViewMixin
from corehq.apps.app_manager.models import get_app
from corehq.apps.hqmedia.cache import BulkMultimediaStatusCache
from corehq.apps.hqmedia.controller import MultimediaBulkUploadController, MultimediaImageUploadController, MultimediaAudioUploadController, MultimediaVideoUploadController
from corehq.apps.hqmedia.decorators import login_with_permission_from_post
from corehq.apps.hqmedia.models import CommCareImage, CommCareAudio, CommCareMultimedia, MULTIMEDIA_PREFIX, CommCareVideo
from corehq.apps.hqmedia.tasks import process_bulk_upload_zip
from corehq.apps.users.decorators import require_permission
from corehq.apps.users.models import Permissions
from dimagi.utils.decorators.memoized import memoized
from dimagi.utils.django.cached_object import CachedObject
from soil.util import expose_download
from django.utils.translation import ugettext as _


class BaseMultimediaView(ApplicationViewMixin, View):

    @method_decorator(require_permission(Permissions.edit_apps, login_decorator=login_with_permission_from_post()))
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
    # todo remove get_media_references
    multimedia = app.get_media_references()
    pathUrls = {}
    for section, types in multimedia['references'].items():
        for media_type, info in types.items():
            for m in info['maps']:
                if m.get('path'):
                    pathUrls[m['path']] = m

    return HttpResponse(json.dumps(pathUrls))


def media_from_path(request, domain, app_id, file_path):
    # Not sure what the intentions were for this. I didn't see it getting used anywhere.
    # Rewrote it to use new media refs.
    # Yedi, care to comment?
    app = get_app(domain, app_id)
    # todo remove get_media_references
    multimedia = app.get_media_references()

    for section, types in multimedia['references'].items():
        for media_type, info in types.items():
            for media_map in info['maps']:
                # [10:] is to remove the 'jr://file/'
                if media_map['path'][10:] == file_path and media_map.get('url'):
                    return HttpResponseRedirect(media_map['url'])

    raise Http404('No Media Found')


class BaseMultimediaUploaderView(BaseMultimediaTemplateView):

    @property
    def page_context(self):
        return {
            'uploaders': self.upload_controllers,
        }

    @property
    def upload_controllers(self):
        """
            Return a list of Upload Controllers
        """
        raise NotImplementedError("You must specify a list of upload controllers")


class MultimediaReferencesView(BaseMultimediaUploaderView):
    name = "hqmedia_references"
    template_name = "hqmedia/references.html"

    @property
    def page_context(self):
        context = super(MultimediaReferencesView, self).page_context
        if self.app is None:
            raise Http404(self)
        context.update({
            "references": self.app.get_references(),
            "object_map": self.app.get_object_map(),
            "totals": self.app.get_reference_totals(),
        })
        return context

    @property
    def upload_controllers(self):
        return [
            MultimediaImageUploadController("hqimage", reverse(ProcessImageFileUploadView.name,
                                                               args=[self.domain, self.app_id])),
            MultimediaAudioUploadController("hqaudio", reverse(ProcessAudioFileUploadView.name,
                                                               args=[self.domain, self.app_id])),
            MultimediaVideoUploadController("hqvideo", reverse(ProcessVideoFileUploadView.name,
                                                               args=[self.domain, self.app_id])),
        ]


class BulkUploadMultimediaView(BaseMultimediaUploaderView):
    name = "hqmedia_bulk_upload"
    template_name = "hqmedia/bulk_upload.html"

    @property
    def upload_controllers(self):
        return [MultimediaBulkUploadController("hqmedia_bulk", reverse(ProcessBulkUploadView.name,
                                                                       args=[self.domain, self.app_id]))]


class BadMediaFileException(Exception):
    pass


class BaseProcessUploadedView(BaseMultimediaView):

    @property
    def username(self):
        return self.request.couch_user.username if self.request.couch_user else None

    @property
    def share_media(self):
        return self.request.POST.get('shared') == 't'

    @property
    def license_used(self):
        return self.request.POST.get('license', '')

    @property
    def author(self):
        return self.request.POST.get('author', '')

    @property
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
            return CommCareMultimedia.get_mime_type(data, filename=self.uploaded_file.name)
        except Exception as e:
            raise BadMediaFileException("There was an error fetching the MIME type of your file. Error: %s" % e)

    def get(self, request, *args, **kwargs):
        return HttpResponseBadRequest("You may only post to this URL.")

    def post(self, request, *args, **kwargs):
        self.errors = []
        response = {}
        try:
            self.validate_file()
            response.update(self.process_upload())
        except BadMediaFileException as e:
            self.errors.append(e.message)
        response.update({
            'errors': self.errors,
        })
        return HttpResponse(json.dumps(response))

    def validate_file(self):
        raise NotImplementedError("You must validate your uploaded file!")

    def process_upload(self):
        raise NotImplementedError("You definitely need to implement this guy.")


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
        if not self.mime_type in self.valid_mime_types():
            raise BadMediaFileException("Your zip file doesn't have a valid mimetype.")
        if not self.uploaded_zip:
            raise BadMediaFileException("There is no ZIP file.")
        if self.uploaded_zip.testzip():
            raise BadMediaFileException("The ZIP file provided was bad.")

    def process_upload(self):
        # save the file w/ soil
        self.uploaded_file.file.seek(0)
        saved_file = expose_download(self.uploaded_file.file.read(), expiry=BulkMultimediaStatusCache.cache_expiry)
        processing_id = saved_file.download_id

        status = BulkMultimediaStatusCache(processing_id)
        status.save()

        process_bulk_upload_zip.delay(processing_id, self.domain, self.app_id,
                                      username=self.username,
                                      share_media=self.share_media,
                                      license_name=self.license_used,
                                      author=self.author,
                                      attribution_notes=self.attribution_notes)
        return status.get_response()

    @classmethod
    def valid_mime_types(cls):
        return [
            'application/zip',
            'application/x-zip',
            'application/octet-stream',
            'application/x-zip-compressed',
        ]


class BaseProcessFileUploadView(BaseProcessUploadedView):
    media_class = None

    @property
    def form_path(self):
        return self.request.POST.get('path', '')

    def validate_file(self):
        def file_ext(filename):
            _, extension = os.path.splitext(filename)
            return extension
        def possible_extensions(filename):
            possible_type = guess_type(filename)[0]
            if not possible_type:
                return []
            return guess_all_extensions(guess_type(filename)[0])

        if not self.mime_type:
            raise BadMediaFileException("Did not process a mime type!")
        base_type = self.mime_type.split('/')[0]
        if base_type not in self.valid_base_types():
            raise BadMediaFileException("Not a valid %s file." % self.media_class.get_nice_name().lower())
        ext = file_ext(self.uploaded_file.name)
        if ext.lower() not in possible_extensions(self.form_path):
            raise BadMediaFileException("File %s has an incorrect file type (%s)." % (self.uploaded_file.name, ext))

    def process_upload(self):
        self.uploaded_file.file.seek(0)
        data = self.uploaded_file.file.read()
        multimedia = self.media_class.get_by_data(data)
        multimedia.attach_data(data,
                               original_filename=self.uploaded_file.name,
                               username=self.username)
        multimedia.add_domain(self.domain, owner=True)
        if self.share_media:
            multimedia.update_or_add_license(self.domain,
                                             type=self.license_used,
                                             author=self.author,
                                             attribution_notes=self.attribution_notes)
        self.app.create_mapping(multimedia, self.form_path)
        return {
            'ref': multimedia.get_media_info(self.form_path),
        }

    @classmethod
    def valid_base_types(cls):
        raise NotImplementedError("You need to specify a list of valid base mime types!")


class ProcessImageFileUploadView(BaseProcessFileUploadView):
    media_class = CommCareImage
    name = "hqmedia_uploader_image"

    @classmethod
    def valid_base_types(cls):
        return ['image']


class ProcessAudioFileUploadView(BaseProcessFileUploadView):
    media_class = CommCareAudio
    name = "hqmedia_uploader_audio"

    @classmethod
    def valid_base_types(cls):
        return ['audio']


class ProcessVideoFileUploadView(BaseProcessFileUploadView):
    media_class = CommCareVideo
    name = "hqmedia_uploader_video"

    @classmethod
    def valid_base_types(cls):
        return ['video']


class CheckOnProcessingFile(BaseMultimediaView):
    name = "hqmedia_check_processing"

    def get(self, request, *args, **kwargs):
        return HttpResponse("workin on it")


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
        self.app.remove_unused_mappings()
        if not self.app.multimedia_map:
            return HttpResponse("You have no multimedia to download.")

        fd, fpath = tempfile.mkstemp()
        tmpfile = os.fdopen(fd, 'w')
        media_zip = zipfile.ZipFile(tmpfile, "w")
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

        wrapper = FileWrapper(open(fpath))
        response = HttpResponse(wrapper, mimetype="application/zip")
        response['Content-Length'] = os.path.getsize(fpath)
        set_file_download(response, 'commcare.zip')
        return response


class MultimediaUploadStatusView(View):
    name = "hqmedia_upload_status"

    @property
    @memoized
    def processing_id(self):
        return self.request.POST.get('processing_id')

    @method_decorator(login_required)
    def dispatch(self, request, *args, **kwargs):
        return super(MultimediaUploadStatusView, self).dispatch(request, *args, **kwargs)

    def get(self, request, *args, **kwargs):
        return HttpResponseBadRequest("Please post to this.")

    def post(self, request, *args, **kwargs):
        if not self.processing_id:
            return HttpResponseBadRequest("A processing_id is required.")
        status = BulkMultimediaStatusCache.get(self.processing_id)
        if status is None:
            # No status could be retrieved from the cache
            fake_status = BulkMultimediaStatusCache(self.processing_id)
            fake_status.complete = True
            fake_status.errors.append(_('There was an issue retrieving the status from the cache. '
                                      'We are looking into it. Please try uploading again.'))
            logging.error("[Multimedia Bulk Upload] Process ID #%s encountered an issue while retrieving "
                          "a status from the cache." % self.processing_id)
            response = fake_status.get_response()
        else:
            response = status.get_response()
        return HttpResponse(json.dumps(response))


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
        obj = CachedObject(str(self.doc_id)
                           + ':' + self.kwargs.get('media_type')
                           + ':' + str(self.thumb))
        if not obj.is_cached():
            data, content_type = self.multimedia.get_display_file()
            if self.thumb:
                data = CommCareImage.get_thumbnail_data(data, self.thumb)
            buffer = StringIO(data)
            metadata = {'content_type': content_type}
            obj.cache_put(buffer, metadata, timeout=0)
        else:
            metadata, buffer = obj.get()
            data = buffer.getvalue()
            content_type = metadata['content_type']
        return HttpResponse(data, mimetype=content_type)
