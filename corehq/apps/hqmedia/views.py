from StringIO import StringIO
from mimetypes import guess_all_extensions, guess_type
import uuid
import zipfile
import logging
import os
from django.contrib.auth.decorators import login_required
import json
import itertools
from django.conf import settings
from django.core.urlresolvers import reverse
from django.utils.decorators import method_decorator
from django.views.generic import View, TemplateView

from couchdbkit.exceptions import ResourceNotFound

from django.http import HttpResponse, Http404, HttpResponseServerError, HttpResponseBadRequest

from django.shortcuts import render
import shutil
from corehq import privileges

from soil import DownloadBase

from corehq.apps.app_manager.decorators import safe_download, require_can_edit_apps
from corehq.apps.app_manager.view_helpers import ApplicationViewMixin
from corehq.apps.app_manager.models import get_app
from corehq.apps.hqmedia.cache import BulkMultimediaStatusCache, BulkMultimediaStatusCacheNfs
from corehq.apps.hqmedia.controller import (
    MultimediaBulkUploadController,
    MultimediaImageUploadController,
    MultimediaAudioUploadController,
    MultimediaVideoUploadController
)
from corehq.apps.hqmedia.decorators import login_with_permission_from_post
from corehq.apps.hqmedia.models import CommCareImage, CommCareAudio, CommCareMultimedia, MULTIMEDIA_PREFIX, CommCareVideo
from corehq.apps.hqmedia.tasks import process_bulk_upload_zip, build_application_zip
from corehq.apps.users.decorators import require_permission
from corehq.apps.users.models import Permissions
from dimagi.utils.decorators.memoized import memoized
from dimagi.utils.django.cached_object import CachedObject
from soil.util import expose_cached_download
from django.utils.translation import ugettext as _
from django_prbac.decorators import requires_privilege_raise404


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


class BaseMultimediaUploaderView(BaseMultimediaTemplateView):

    @property
    def page_context(self):
        return {
            'uploaders': self.upload_controllers,
            "sessionid": self.request.COOKIES.get('sessionid'),
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
            "sessionid": self.request.COOKIES.get('sessionid'),
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
        if hasattr(self.uploaded_file, 'temporary_file_path') and settings.SHARED_DRIVE_CONF.temp_dir:
            processing_id = uuid.uuid4().hex
            path = settings.SHARED_DRIVE_CONF.get_temp_file(suffix='.upload')
            shutil.move(self.uploaded_file.temporary_file_path(), path)
            status = BulkMultimediaStatusCacheNfs(processing_id, path)
            status.save()
        else:
            self.uploaded_file.file.seek(0)
            saved_file = expose_cached_download(self.uploaded_file.file.read(), expiry=BulkMultimediaStatusCache.cache_expiry)
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

    @property
    def file_ext(self):
        def file_ext(filename):
            _, extension = os.path.splitext(filename)
            return extension
        return file_ext(self.uploaded_file.name)

    def validate_file(self):
        def possible_extensions(filename):
            possible_type = guess_type(filename)[0]
            if not possible_type:
                return []
            return guess_all_extensions(guess_type(filename)[0])

        if not self.mime_type:
            raise BadMediaFileException(_("Did not process a mime type!"))
        base_type = self.mime_type.split('/')[0]
        if base_type not in self.valid_base_types():
            raise BadMediaFileException(
                _("Not a valid %s file.")
                % self.media_class.get_nice_name().lower()
            )
        if self.file_ext.lower() not in possible_extensions(self.form_path):
            raise BadMediaFileException(
                _("File {name}s has an incorrect file type {ext}.").format(
                    name=self.uploaded_file.name,
                    ext=self.file_ext,
                )
            )

    def process_upload(self):
        self.uploaded_file.file.seek(0)
        self.data = self.uploaded_file.file.read()
        multimedia = self.media_class.get_by_data(self.data)
        multimedia.attach_data(self.data,
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


class ProcessLogoFileUploadView(ProcessImageFileUploadView):
    name = "hqmedia_uploader_logo"

    @method_decorator(requires_privilege_raise404(privileges.COMMCARE_LOGO_UPLOADER))
    def post(self, request, *args, **kwargs):
        return super(ProcessLogoFileUploadView, self).post(request, *args, **kwargs)

    @property
    def form_path(self):
        return ("jr://file/commcare/logo/data/%s%s"
                % (self.filename, self.file_ext))

    @property
    def filename(self):
        return self.kwargs.get('logo_name')

    def process_upload(self):
        if self.app.logo_refs is None:
            self.app.logo_refs = {}
        ref = super(
            ProcessLogoFileUploadView, self
        ).process_upload()
        self.app.logo_refs[self.filename] = ref['ref']
        self.app.save()
        return ref


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


class ProcessTextFileUploadView(BaseProcessFileUploadView):
    media_class = CommCareMultimedia
    name = "hqmedia_uploader_text"

    @classmethod
    def valid_base_types(cls):
        return ['text']

    def process_upload(self):
        ret = super(ProcessTextFileUploadView, self).process_upload()
        ret['text'] = self.data
        return ret

class RemoveLogoView(BaseMultimediaView):
    name = "hqmedia_remove_logo"

    @property
    def logo_slug(self):
        if self.request.method == 'POST':
            return self.request.POST.get('logo_slug')
        return None

    @method_decorator(requires_privilege_raise404(privileges.COMMCARE_LOGO_UPLOADER))
    def post(self, *args, **kwargs):
        if self.logo_slug in self.app.logo_refs:
            del self.app.logo_refs[self.logo_slug]
            self.app.save()
        return HttpResponse()

class CheckOnProcessingFile(BaseMultimediaView):
    name = "hqmedia_check_processing"

    def get(self, request, *args, **kwargs):
        return HttpResponse("workin on it")


def iter_media_files(media_objects):
    """
    take as input the output of get_media_objects
    and return an iterator of (path, data) tuples for the media files
    as they should show up in the .zip
    as well as a list of error messages

    as a side effect of implementation,
    errors will not include all error messages until the iterator is exhausted

    """
    errors = []

    def _media_files():
        for path, media in media_objects:
            try:
                data, _ = media.get_display_file()
                folder = path.replace(MULTIMEDIA_PREFIX, "")
                if not isinstance(data, unicode):
                    yield os.path.join(folder), data
            except NameError as e:
                errors.append("%(path)s produced an ERROR: %(error)s" % {
                    'path': path,
                    'error': e,
                })
    return _media_files(), errors


def iter_app_files(app, include_multimedia_files, include_index_files):
    file_iterator = []
    errors = []
    if include_multimedia_files:
        app.remove_unused_mappings()
        file_iterator, errors = iter_media_files(app.get_media_objects())
    if include_index_files:
        from corehq.apps.app_manager.views import iter_index_files
        index_files, index_file_errors = iter_index_files(app)
        if index_file_errors:
            errors.extend(index_file_errors)
        file_iterator = itertools.chain(file_iterator, index_files)

    return file_iterator, errors


class DownloadMultimediaZip(View, ApplicationViewMixin):
    """
    This is where the Multimedia for an application gets generated.
    Expects domain and app_id to be in its args

    """

    name = "download_multimedia_zip"
    compress_zip = False
    zip_name = 'commcare.zip'
    include_multimedia_files = True
    include_index_files = False

    def check_before_zipping(self):
        if not self.app.multimedia_map and self.include_multimedia_files:
            return HttpResponse("You have no multimedia to download.")

    def log_errors(self, errors):
        logging.error(
            "Error downloading multimedia ZIP "
            "for domain %s and application %s." % (
                self.domain, self.app_id)
        )
        return HttpResponseServerError(
            "Errors were encountered while "
            "retrieving media for this application.<br /> %s" % (
                "<br />".join(errors))
        )

    def get(self, request, *args, **kwargs):
        assert self.include_multimedia_files or self.include_index_files
        error_response = self.check_before_zipping()
        if error_response:
            return error_response

        download = DownloadBase()
        download.set_task(build_application_zip.delay(
            include_multimedia_files=self.include_multimedia_files,
            include_index_files=self.include_index_files,
            app=self.app,
            download_id=download.download_id,
            compress_zip=self.compress_zip,
            filename=self.zip_name)
        )
        return download.get_start_response()

    @method_decorator(safe_download)
    def dispatch(self, request, *args, **kwargs):
        return super(DownloadMultimediaZip, self).dispatch(request, *args, **kwargs)


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
        return HttpResponse(data, content_type=content_type)
