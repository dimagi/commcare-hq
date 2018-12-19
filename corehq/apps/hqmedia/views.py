from __future__ import absolute_import
from __future__ import unicode_literals
from mimetypes import guess_all_extensions, guess_type
import uuid
import zipfile
import io
import logging
import os
from django.contrib.auth.decorators import login_required
import json
import itertools
from collections import defaultdict
from django.conf import settings
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST
from django.views.generic import View, TemplateView

from couchdbkit.exceptions import ResourceNotFound, ResourceConflict
from lxml import etree

from django.http import HttpResponse, Http404, HttpResponseServerError, HttpResponseBadRequest

from django.shortcuts import render
import shutil
from corehq import privileges
from corehq.apps.app_manager.const import TARGET_COMMCARE, TARGET_COMMCARE_LTS
from corehq.apps.hqmedia.exceptions import BadMediaFileException
from corehq.util.files import file_extention_from_filename
from corehq.util.workbook_reading import SpreadsheetFileExtError

from soil import DownloadBase

from couchexport.export import export_raw
from couchexport.models import Format
from couchexport.shortcuts import export_response
from corehq import toggles
from corehq.middleware import always_allow_browser_caching
from corehq.apps.accounting.utils import domain_has_privilege
from corehq.apps.app_manager.dbaccessors import get_app
from corehq.apps.app_manager.decorators import require_can_edit_apps, safe_cached_download
from corehq.apps.app_manager.view_helpers import ApplicationViewMixin
from corehq.apps.app_manager.views.media_utils import interpolate_media_path
from corehq.apps.case_importer.tracking.filestorage import TransientFileStore
from corehq.apps.case_importer.util import open_spreadsheet_download_ref, get_spreadsheet, ALLOWED_EXTENSIONS
from corehq.apps.domain.decorators import login_and_domain_required
from corehq.apps.hqmedia.cache import BulkMultimediaStatusCache, BulkMultimediaStatusCacheNfs
from corehq.apps.hqmedia.controller import (
    MultimediaBulkUploadController,
    MultimediaImageUploadController,
    MultimediaAudioUploadController,
    MultimediaVideoUploadController
)
from corehq.apps.hqmedia.models import CommCareImage, CommCareAudio, CommCareMultimedia, MULTIMEDIA_PREFIX, CommCareVideo
from corehq.apps.hqmedia.tasks import process_bulk_upload_zip, build_application_zip
from corehq.apps.hqwebapp.views import BaseSectionPageView
from corehq.apps.users.decorators import require_permission
from corehq.apps.users.models import Permissions
from dimagi.utils.web import json_response
from memoized import memoized
from soil.util import expose_cached_download
from django.utils.translation import ugettext as _, ugettext_noop
from django_prbac.decorators import requires_privilege_raise404
import six


transient_file_store = TransientFileStore("hqmedia_upload_paths", timeout=1 * 60 * 60)


class BaseMultimediaView(ApplicationViewMixin, BaseSectionPageView):

    @method_decorator(require_permission(Permissions.edit_apps, login_decorator=login_and_domain_required))
    def dispatch(self, request, *args, **kwargs):
        return super(BaseMultimediaView, self).dispatch(request, *args, **kwargs)


class BaseMultimediaTemplateView(BaseMultimediaView, TemplateView):
    """
        The base view for all the multimedia templates.
    """
    @property
    def section_name(self):
        return self.app.name

    @property
    def page_url(self):
        return reverse(self.urlname, args=[self.domain, self.app.get_id])

    @property
    def section_url(self):
        return reverse("app_settings", args=[self.domain, self.app.get_id])

    @property
    def page_context(self, **kwargs):
        context = super(BaseMultimediaTemplateView, self).page_context
        views = [MultimediaReferencesView, BulkUploadMultimediaView]
        if toggles.BULK_UPDATE_MULTIMEDIA_PATHS.enabled_for_request(self.request):
            views.append(ManageMultimediaPathsView)
        context.update({
            "domain": self.domain,
            "app": self.app,
            "navigation_sections": (
                (_("Multimedia"), [
                    {
                        'title': view.page_title,
                        'url': reverse(view.urlname, args=[self.domain, self.app.id]),
                        'is_active': view.urlname == self.urlname,
                    } for view in views
                ]),
            ),
        })
        return context

    def render_to_response(self, context, **response_kwargs):
        return render(self.request, self.template_name, context)


class BaseMultimediaUploaderView(BaseMultimediaTemplateView):

    @property
    def page_context(self):
        context = super(BaseMultimediaUploaderView, self).page_context
        context.update({
            'uploaders': self.upload_controllers,
            'uploaders_js': [u.js_options for u in self.upload_controllers],
            "sessionid": self.request.COOKIES.get('sessionid'),
        })
        return context

    @property
    def upload_controllers(self):
        """
            Return a list of Upload Controllers
        """
        raise NotImplementedError("You must specify a list of upload controllers")


class MultimediaReferencesView(BaseMultimediaUploaderView):
    urlname = "hqmedia_references"
    template_name = "hqmedia/references.html"
    page_title = ugettext_noop("Multimedia Reference Checker")

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
            MultimediaImageUploadController("hqimage", reverse(ProcessImageFileUploadView.urlname,
                                                               args=[self.domain, self.app_id])),
            MultimediaAudioUploadController("hqaudio", reverse(ProcessAudioFileUploadView.urlname,
                                                               args=[self.domain, self.app_id])),
            MultimediaVideoUploadController("hqvideo", reverse(ProcessVideoFileUploadView.urlname,
                                                               args=[self.domain, self.app_id])),
        ]


class BulkUploadMultimediaView(BaseMultimediaUploaderView):
    urlname = "hqmedia_bulk_upload"
    template_name = "hqmedia/bulk_upload.html"
    page_title = ugettext_noop("Bulk Upload Multimedia")

    @property
    def parent_pages(self):
        return [{
            'title': _("Multimedia Reference Checker"),
            'url': reverse(MultimediaReferencesView.urlname, args=[self.domain, self.app.get_id]),
        }]

    @property
    def upload_controllers(self):
        return [MultimediaBulkUploadController("hqmedia_bulk", reverse(ProcessBulkUploadView.urlname,
                                                                       args=[self.domain, self.app_id]))]


@method_decorator(toggles.BULK_UPDATE_MULTIMEDIA_PATHS.required_decorator(), name='dispatch')
@method_decorator(require_can_edit_apps, name='dispatch')
class ManageMultimediaPathsView(BaseMultimediaTemplateView):
    urlname = "manage_multimedia_paths"
    template_name = "hqmedia/manage_paths.html"
    page_title = ugettext_noop("Manage Multimedia Paths")

    @property
    def parent_pages(self):
        return [{
            'title': _("Multimedia Reference Checker"),
            'url': reverse(MultimediaReferencesView.urlname, args=[self.domain, self.app.get_id]),
        }]


@toggles.BULK_UPDATE_MULTIMEDIA_PATHS.required_decorator()
@require_can_edit_apps
@require_GET
def download_multimedia_paths(request, domain, app_id):
    from corehq.apps.hqmedia.view_helpers import download_multimedia_paths_rows
    app = get_app(domain, app_id)

    headers = ((_("Paths"), (_("Path in Application"), _("Usages"))),)
    rows = download_multimedia_paths_rows(app)

    temp = io.BytesIO()
    export_raw(headers, rows, temp)
    filename = '{app_name} v.{app_version} - App Multimedia Paths'.format(
        app_name=app.name,
        app_version=app.version)
    return export_response(temp, Format.XLS_2007, filename)


@toggles.BULK_UPDATE_MULTIMEDIA_PATHS.required_decorator()
@require_can_edit_apps
@require_POST
def validate_multimedia_paths(request, domain, app_id):
    if not request.FILES:
        return json_response({
            'error': _("Please choose an Excel file to import.")
        })

    handle = request.FILES['file']

    extension = os.path.splitext(handle.name)[1][1:].strip().lower()
    if extension not in ALLOWED_EXTENSIONS:
        return json_response({
            'error': _("Please choose a file with one of the following extensions: "
                       "{}").format(", ".join(ALLOWED_EXTENSIONS))
        })

    meta = transient_file_store.write_file(handle, handle.name, domain)
    file_id = meta.identifier

    f = transient_file_store.get_tempfile_ref_for_contents(file_id)
    try:
        open_spreadsheet_download_ref(f)
    except SpreadsheetFileExtError:
        return json_response({
            'error': _("File does not appear to be an Excel file. Please choose another file.")
        })

    from corehq.apps.hqmedia.view_helpers import validate_multimedia_paths_rows
    app = get_app(domain, app_id)
    with get_spreadsheet(f) as spreadsheet:
        (errors, warnings) = validate_multimedia_paths_rows(app, spreadsheet.iter_rows())

    return json_response({
        'complete': 1,
        'file_id': file_id,
        'errors': errors,
        'warnings': warnings,
    })


@toggles.BULK_UPDATE_MULTIMEDIA_PATHS.required_decorator()
@require_can_edit_apps
@require_POST
def update_multimedia_paths(request, domain, app_id):
    file_id = request.POST.get('file_id')

    f = transient_file_store.get_tempfile_ref_for_contents(file_id)

    if not f:
        return json_response({
            'error': _("Could not find file. Please re-upload file.")
        })

    app = get_app(domain, app_id)
    from corehq.apps.hqmedia.view_helpers import validate_multimedia_paths_rows
    with get_spreadsheet(f) as spreadsheet:
        rows = list(spreadsheet.iter_rows())
        (errors, warnings) = validate_multimedia_paths_rows(app, rows)
        if len(errors):
            return json_response({
                'complete': 1,
                'errors': errors,
            })

        # Master list of old_path => new_path
        paths = {row[0]: interpolate_media_path(row[1]) for row in rows}

        # Update module and form references
        success_counts = defaultdict(lambda: 0)
        xforms_by_id = defaultdict(lambda: None)    # cache forms rather than parsing repeatedly
        dirty_xform_ids = set()
        for old_path, new_path in six.iteritems(paths):
            for module in app.modules:
                success_counts[module.unique_id] += module.rename_media(old_path, new_path)
                if module.case_list_form.form_id:
                    success_counts[module.unique_id] += module.case_list_form.rename_media(old_path, new_path)
                if hasattr(module, 'case_list') and module.case_list.show:
                    success_counts[module.unique_id] += module.case_list.rename_media(old_path, new_path)
                for name, details, display in module.get_details():
                    # Case list lookup
                    if display and details.display == 'short' and details.lookup_enabled and details.lookup_image:
                        if details.lookup_image == old_path:
                            details.lookup_image = new_path
                            success_counts[module.unique_id] += 1

                    # Icons in case details
                    for column in details.get_columns():
                        if column.format == 'enum-image':
                            for map_item in column.enum:
                                for lang, icon in six.iteritems(map_item.value):
                                    if icon == old_path:
                                        map_item.value[lang] = new_path
                                        success_counts[module.unique_id] += 1
                for form in module.forms:
                    success_counts[form.unique_id] += form.rename_media(old_path, new_path)
                    if not xforms_by_id[form.unique_id]:
                        xforms_by_id[form.unique_id] = form.wrapped_xform()
                    update_count = xforms_by_id[form.unique_id].rename_media(old_path, new_path)
                    success_counts[form.unique_id] += update_count
                    if update_count:
                        dirty_xform_ids.add(form.unique_id)

        # Update any form xml that changed
        for module in app.modules:
            for form in module.forms:
                if form.unique_id in dirty_xform_ids:
                    form.source = etree.tostring(xforms_by_id[form.unique_id].xml).decode('utf-8')

        # Update app's master map of multimedia
        for old_path, new_path in six.iteritems(paths):
            app.multimedia_map.update({
                new_path: app.multimedia_map[old_path],
            })

        # Put together success messages
        successes = []
        for module in app.modules:
            if success_counts[module.unique_id]:
                successes.append(_("{} item(s) updated in <a href='{}' target='_blank'>{}</a>").format(
                                 success_counts[module.unique_id],
                                 reverse("view_module", args=[domain, app.id, module.unique_id]),
                                 module.default_name()))
            for form in module.forms:
                if success_counts[form.unique_id]:
                    successes.append(_("{} item(s) updated in <a href='{}' target='_blank'>{}</a>").format(
                                     success_counts[form.unique_id],
                                     reverse("view_form", args=[domain, app.id, form.unique_id]),
                                     "{} > {}".format(module.default_name(), form.default_name())))

        app.save()

        # Force all_media to reset
        app.all_media.reset_cache(app)
        app.all_media_paths.reset_cache(app)

        # Warn if any old paths remain in app (because they're used in a place this function doesn't know about)
        warnings = []
        app.remove_unused_mappings()
        app_paths = {m.path: True for m in app.all_media()}
        for old_path, new_path in six.iteritems(paths):
            if old_path in app_paths:
                warnings.append(_("Could not completely update path <code>{}</code>, "
                                  "please check app for remaining references.").format(old_path))

    return json_response({
        'complete': 1,
        'successes': successes,
        'warnings': warnings,
    })


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

    @method_decorator(require_permission(Permissions.edit_apps, login_decorator=login_and_domain_required))
    # YUI js uploader library doesn't support csrf
    @csrf_exempt
    def dispatch(self, request, *args, **kwargs):
        return super(BaseMultimediaView, self).dispatch(request, *args, **kwargs)

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
        response_class = HttpResponseBadRequest if self.errors else HttpResponse
        return response_class(json.dumps(response))

    def validate_file(self, replace_diff_ext=False):
        raise NotImplementedError("You must validate your uploaded file!")

    def process_upload(self):
        raise NotImplementedError("You definitely need to implement this guy.")


class ProcessBulkUploadView(BaseProcessUploadedView):
    urlname = "hqmedia_uploader_bulk"

    @property
    @memoized
    def uploaded_zip(self):
        try:
            self.uploaded_file.file.seek(0)
            return zipfile.ZipFile(self.uploaded_file)
        except Exception as e:
            msg = _("There was an issue processing the zip file you provided. Error: %s")
            raise BadMediaFileException(msg % e)

    def validate_file(self, replace_diff_ext=False):
        if not self.mime_type in self.valid_mime_types():
            raise BadMediaFileException(_("Uploaded file is not a ZIP file."))
        if not self.uploaded_zip:
            raise BadMediaFileException(_("There is no ZIP file."))
        if self.uploaded_zip.testzip():
            raise BadMediaFileException(_("Unable to extract the ZIP file."))

    def process_upload(self):
        if hasattr(self.uploaded_file, 'temporary_file_path') and settings.SHARED_DRIVE_CONF.temp_dir:
            processing_id = uuid.uuid4().hex
            path = settings.SHARED_DRIVE_CONF.get_temp_file(suffix='.upload')
            shutil.move(self.uploaded_file.temporary_file_path(), path)
            status = BulkMultimediaStatusCacheNfs(processing_id, path)
            status.save()
        else:
            self.uploaded_file.file.seek(0)
            saved_file = expose_cached_download(
                self.uploaded_file.file.read(),
                expiry=BulkMultimediaStatusCache.cache_expiry,
                file_extension=file_extention_from_filename(self.uploaded_file.name),
            )
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
    def original_path(self):
        return self.request.POST.get('originalPath')

    @property
    def file_ext(self):
        def file_ext(filename):
            _, extension = os.path.splitext(filename)
            return extension
        return file_ext(self.uploaded_file.name)

    @property
    def orig_ext(self):
        if self.original_path is None:
            return self.file_ext
        return '.{}'.format(self.original_path.split('.')[-1])

    def validate_file(self, replace_diff_ext=False):
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
                _("File {name} has an incorrect file type {ext}.").format(
                    name=self.uploaded_file.name,
                    ext=self.file_ext,
                )
            )
        if not replace_diff_ext and self.file_ext.lower() != self.orig_ext.lower():
            raise BadMediaFileException(_(
                "The file type of {name} of '{ext}' does not match the "
                "file type of the original media file '{orig_ext}'. To change "
                "file types, please upload directly from the "
                "Form Builder."
            ).format(
                name=self.uploaded_file.name,
                ext=self.file_ext.lower(),
                orig_ext=self.orig_ext.lower(),
            ))

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
    urlname = "hqmedia_uploader_image"

    @classmethod
    def valid_base_types(cls):
        return ['image']


class ProcessLogoFileUploadView(ProcessImageFileUploadView):
    urlname = "hqmedia_uploader_logo"

    @method_decorator(requires_privilege_raise404(privileges.COMMCARE_LOGO_UPLOADER))
    def post(self, request, *args, **kwargs):
        return super(ProcessLogoFileUploadView, self).post(request, *args, **kwargs)

    @property
    def form_path(self):
        return ("jr://file/commcare/logo/data/%s%s"
                % (self.filename, self.file_ext))

    def validate_file(self, replace_diff_ext=True):
        return super(ProcessLogoFileUploadView, self).validate_file(replace_diff_ext)

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
        if self.app.doc_type == 'LinkedApplication':
            self.app.linked_app_logo_refs[self.filename] = ref['ref']
        self.app.save()
        return ref


class ProcessAudioFileUploadView(BaseProcessFileUploadView):
    media_class = CommCareAudio
    urlname = "hqmedia_uploader_audio"

    @classmethod
    def valid_base_types(cls):
        return ['audio']


class ProcessVideoFileUploadView(BaseProcessFileUploadView):
    media_class = CommCareVideo
    urlname = "hqmedia_uploader_video"

    @classmethod
    def valid_base_types(cls):
        return ['video']


class ProcessTextFileUploadView(BaseProcessFileUploadView):
    media_class = CommCareMultimedia
    urlname = "hqmedia_uploader_text"

    @classmethod
    def valid_base_types(cls):
        return ['text']


class ProcessDetailPrintTemplateUploadView(ProcessTextFileUploadView):
    urlname = "hqmedia_uploader_detail_print_template"

    @method_decorator(toggles.CASE_DETAIL_PRINT.required_decorator())
    def post(self, request, *args, **kwargs):
        return super(ProcessDetailPrintTemplateUploadView, self).post(request, *args, **kwargs)

    @property
    def form_path(self):
        return ("jr://file/commcare/text/module_%s_detail_print%s"
                % (self.module_unique_id, self.file_ext))

    @property
    def module_unique_id(self):
        return self.kwargs.get('module_unique_id')

    def validate_file(self, replace_diff_ext=True):
        return super(ProcessDetailPrintTemplateUploadView, self).validate_file(replace_diff_ext)

    def process_upload(self):
        ref = super(
            ProcessDetailPrintTemplateUploadView, self
        ).process_upload()
        self.app.get_module_by_unique_id(self.module_unique_id).case_details.long.print_template = ref['ref']
        self.app.save()
        return ref


class RemoveDetailPrintTemplateView(BaseMultimediaView):
    urlname = "hqmedia_remove_detail_print_template"

    @property
    def module_unique_id(self):
        if self.request.method == 'POST':
            return self.request.POST.get('module_unique_id')
        return None

    @method_decorator(toggles.CASE_DETAIL_PRINT.required_decorator())
    def post(self, *args, **kwargs):
        del self.app.get_module_by_unique_id(self.module_unique_id).case_details.long.print_template
        self.app.save()
        return HttpResponse()


class RemoveLogoView(BaseMultimediaView):
    urlname = "hqmedia_remove_logo"

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
    urlname = "hqmedia_check_processing"

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
                if not isinstance(data, six.text_type):
                    yield os.path.join(folder), data
            except NameError as e:
                errors.append("%(path)s produced an ERROR: %(error)s" % {
                    'path': path,
                    'error': e,
                })
    return _media_files(), errors


def iter_app_files(app, include_multimedia_files, include_index_files, build_profile_id=None, download_targeted_version=False):
    file_iterator = []
    errors = []
    index_file_count = 0
    multimedia_file_count = 0
    if include_multimedia_files:
        app.remove_unused_mappings()
        languages = None
        if build_profile_id is not None:
            languages = app.build_profiles[build_profile_id].langs
        media_objects = list(app.get_media_objects(languages=languages))
        multimedia_file_count = len(media_objects)
        file_iterator, errors = iter_media_files(media_objects)
    if include_index_files:
        index_files, index_file_errors, index_file_count = iter_index_files(
            app, build_profile_id=build_profile_id, download_targeted_version=download_targeted_version
        )
        if index_file_errors:
            errors.extend(index_file_errors)
        file_iterator = itertools.chain(file_iterator, index_files)

    return file_iterator, errors, (index_file_count + multimedia_file_count)


class DownloadMultimediaZip(View, ApplicationViewMixin):
    """
    This is where the Multimedia for an application gets generated.
    Expects domain and app_id to be in its args

    """

    urlname = "download_multimedia_zip"
    compress_zip = False
    include_multimedia_files = True
    include_index_files = False

    @property
    def zip_name(self):
        return 'commcare_v{}.zip'.format(self.app.version)

    def check_before_zipping(self):
        if not self.app.multimedia_map and self.include_multimedia_files:
            return HttpResponse("You have no multimedia to download.")

    def get(self, request, *args, **kwargs):
        assert self.include_multimedia_files or self.include_index_files
        error_response = self.check_before_zipping()
        if error_response:
            return error_response

        message = request.GET['message'] if 'message' in request.GET else None
        download = DownloadBase(message=message)
        build_profile_id = None
        if domain_has_privilege(request.domain, privileges.BUILD_PROFILES):
            build_profile_id = request.GET.get('profile')
        download_targeted_version = request.GET.get('download_targeted_version') == 'true'
        download.set_task(build_application_zip.delay(
            include_multimedia_files=self.include_multimedia_files,
            include_index_files=self.include_index_files,
            app=self.app,
            download_id=download.download_id,
            compress_zip=self.compress_zip,
            filename=self.zip_name,
            build_profile_id=build_profile_id,
            download_targeted_version=download_targeted_version,
        ))
        return download.get_start_response()

    @method_decorator(safe_cached_download)
    def dispatch(self, request, *args, **kwargs):
        return super(DownloadMultimediaZip, self).dispatch(request, *args, **kwargs)


class MultimediaUploadStatusView(View):
    urlname = "hqmedia_upload_status"

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
    urlname = "hqmedia_download"

    @always_allow_browser_caching
    def dispatch(self, request, *args, **kwargs):
        return super(ViewMultimediaFile, self).dispatch(request, *args, **kwargs)

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
        if self.thumb:
            data = CommCareImage.get_thumbnail_data(data, self.thumb)
        response = HttpResponse(data, content_type=content_type)
        response['Content-Disposition'] = 'filename="download{}"'.format(self.multimedia.get_file_extension())
        return response


def iter_index_files(app, build_profile_id=None, download_targeted_version=False):
    from corehq.apps.app_manager.views.download import download_index_files
    from dimagi.utils.logging import notify_exception
    skip_files = [
        text_format.format(suffix)
        for text_format in ['profile{}.xml', 'profile{}.ccpr', 'media_profile{}.xml']
        for suffix in ['', '-' + TARGET_COMMCARE, '-' + TARGET_COMMCARE_LTS]
    ]
    text_extensions = ('.xml', '.ccpr', '.txt')
    files = []
    errors = []

    def _get_name(f):
        return {
            'media_profile{}.ccpr'.format(suffix): 'profile.ccpr'
            for suffix in ['', '-' + TARGET_COMMCARE, '-' + TARGET_COMMCARE_LTS]
        }.get(f, f)

    def _encode_if_unicode(s):
        return s.encode('utf-8') if isinstance(s, six.text_type) else s

    def _files(files):
        for name, f in files:
            if download_targeted_version and name == 'media_profile.ccpr':
                continue
            elif not download_targeted_version and name in [
                'media_profile-{}.ccpr'.format(suffix) for suffix in [TARGET_COMMCARE, TARGET_COMMCARE_LTS]
            ]:
                continue
            if build_profile_id is not None:
                name = name.replace(build_profile_id + '/', '')
            if name not in skip_files:
                # TODO: make RemoteApp.create_all_files not return media files
                extension = os.path.splitext(name)[1]
                data = _encode_if_unicode(f) if extension in text_extensions else f
                yield (_get_name(name), data)

    def _download_index_files(app, build_profile_id, is_retry=False):
        try:
            return download_index_files(app, build_profile_id)
        except ResourceConflict as e:
            if is_retry:
                raise e
            return _download_index_files(app, build_profile_id, is_retry=True)

    try:
        files = _download_index_files(app, build_profile_id)
    except Exception as e:
        notify_exception(None, e.message)
        errors = [six.text_type(e)]

    return _files(files), errors, len(files)
