import io
import itertools
import json
import os
import shutil
import uuid
import zipfile
from datetime import datetime
from mimetypes import guess_all_extensions, guess_type

from django.conf import settings
from django.contrib import messages
from django.http import (
    Http404,
    HttpResponse,
    HttpResponseBadRequest,
    HttpResponseRedirect,
    JsonResponse,
)
from django.http.response import HttpResponseServerError
from django.shortcuts import render
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.translation import gettext as _
from django.utils.translation import gettext_noop
from django.views.decorators.http import require_GET
from django.views.generic import TemplateView, View

from couchdbkit.exceptions import ResourceConflict, ResourceNotFound
from django_prbac.decorators import requires_privilege_raise404
from memoized import memoized

from couchexport.export import export_raw
from couchexport.models import Format
from couchexport.shortcuts import export_response
from soil import DownloadBase
from soil.exceptions import TaskFailedError
from soil.util import expose_cached_download, get_download_context

from corehq import privileges, toggles
from corehq.apps.accounting.utils import domain_has_privilege
from corehq.apps.app_manager.const import TARGET_COMMCARE, TARGET_COMMCARE_LTS
from corehq.apps.app_manager.dbaccessors import get_app
from corehq.apps.app_manager.decorators import (
    require_can_edit_apps,
    safe_cached_download,
)
from corehq.apps.app_manager.util import is_linked_app
from corehq.apps.app_manager.view_helpers import ApplicationViewMixin
from corehq.apps.case_importer.tracking.filestorage import TransientFileStore
from corehq.apps.case_importer.util import (
    get_spreadsheet,
    open_spreadsheet_download_ref,
)
from corehq.apps.domain.decorators import login_and_domain_required
from corehq.apps.hqmedia.cache import (
    BulkMultimediaStatusCache,
    BulkMultimediaStatusCacheNfs,
)
from corehq.apps.hqmedia.controller import (
    MultimediaAudioUploadController,
    MultimediaImageUploadController,
    MultimediaVideoUploadController,
)
from corehq.apps.hqmedia.exceptions import BadMediaFileException
from corehq.apps.hqmedia.models import (
    MULTIMEDIA_PREFIX,
    CommCareAudio,
    CommCareImage,
    CommCareMultimedia,
    CommCareVideo,
)
from corehq.apps.hqmedia.tasks import (
    build_application_zip,
    process_bulk_upload_zip,
)
from corehq.apps.hqwebapp.utils import get_bulk_upload_form
from corehq.apps.hqwebapp.views import BaseSectionPageView
from corehq.apps.translations.utils import get_file_content_from_workbook
from corehq.apps.users.decorators import require_permission
from corehq.apps.users.models import HqPermissions
from corehq.middleware import always_allow_browser_caching
from corehq.util.files import file_extention_from_filename
from corehq.util.workbook_reading import valid_extensions, SpreadsheetFileExtError

transient_file_store = TransientFileStore("hqmedia_upload_paths", timeout=1 * 60 * 60)


class BaseMultimediaView(ApplicationViewMixin, BaseSectionPageView):

    @method_decorator(require_permission(HqPermissions.edit_apps, login_decorator=login_and_domain_required))
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

        def _section(view, icon):
            return {
                'title': view.page_title,
                'url': reverse(view.urlname, args=[self.domain, self.app.id]),
                'is_active': view.urlname == self.urlname,
                'icon': f'fa {icon}'
            }

        sections = [
            _section(MultimediaReferencesView, 'fa-check-square'),
            _section(BulkUploadMultimediaView, 'fa-cloud-upload-alt'),
        ]
        if toggles.BULK_UPDATE_MULTIMEDIA_PATHS.enabled_for_request(self.request):
            sections.append(_section(ManageMultimediaPathsView, 'fa-route'))
            if len(self.app.langs) > 1:
                sections.append(_section(MultimediaAudioTranslatorFileView, 'fa-volume-up'))
                sections.append(_section(MultimediaTranslationsCoverageView, 'fa-globe'))

        context.update({
            "domain": self.domain,
            "app": self.app,
            "navigation_sections": ((_("Multimedia"), sections),),
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
    page_title = gettext_noop("Multimedia Reference Checker")

    @property
    def page_context(self):
        context = super(MultimediaReferencesView, self).page_context
        if self.app is None:
            raise Http404(self)
        context.update({
            "multimedia_state": self.app.check_media_state(),
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

    def get(self, request, *args, **kwargs):
        if request.GET.get('json', None):
            only_missing = request.GET.get('only_missing', 'false') == 'true'
            include_total = request.GET.get('include_total', 'true') == 'true'
            lang = request.GET.get('lang', None) or None    # needs to be None if not present, not ''
            query = request.GET.get('query', '')
            media_class = request.GET.get('media_class', '')
            limit = int(request.GET.get('limit', 5))
            page = int(request.GET.get('page', 1))

            (total, references) = self._process_references(page,
                                                           limit,
                                                           lang=lang,
                                                           query=query,
                                                           media_class=media_class,
                                                           only_missing=only_missing,
                                                           include_total=include_total)
            multimedia_map = {r['path']: self.app.multimedia_map[r['path']]
                              for r in references
                              if r['path'] in self.app.multimedia_map}
            object_map = self.app.get_object_map(multimedia_map=multimedia_map)

            data = {
                "references": references,
                "object_map": object_map,
            }
            if include_total:
                data.update({
                    "totals": self.app.get_reference_totals(),
                    "total_rows": total,
                })
            return JsonResponse(data)
        return super(MultimediaReferencesView, self).get(request, *args, **kwargs)

    def _process_references(self, page, limit, lang=None, query=None, media_class=None,
                            only_missing=False, include_total=True):
        reference_index = 0
        references = []
        start = limit * (page - 1)
        end = start + limit
        if query:
            query = query.lower()

        def _add_references(source, reference_index, references):
            if reference_index > end and not include_total:
                return (reference_index, references)
            media = source.get_references(lang=lang)
            media_classes = [media_class] if media_class else ["CommCareImage", "CommCareAudio", "CommCareVideo"]
            media = [m for m in media if m['media_class'] in media_classes]
            if query:
                media = [m for m in media if query in m['path'].lower()]
            if only_missing:
                media = [m for m in media if m['path'] not in self.app.multimedia_map]
            for m in media:
                if reference_index >= start and reference_index < end:
                    references.append(m)
                reference_index += 1
            return (reference_index, references)

        for module in self.app.get_modules():
            (reference_index, references) = _add_references(module, reference_index, references)
            for form in module.get_forms():
                (reference_index, references) = _add_references(form, reference_index, references)
        return (reference_index, references)


class BulkUploadMultimediaView(BaseMultimediaTemplateView):
    urlname = "hqmedia_bulk_upload"
    template_name = "hqmedia/bulk_upload.html"
    page_title = gettext_noop("Bulk Upload Multimedia")

    @property
    def parent_pages(self):
        return [{
            'title': _("Multimedia Reference Checker"),
            'url': reverse(MultimediaReferencesView.urlname, args=[self.domain, self.app.get_id]),
        }]

    @property
    def page_context(self):
        context = super().page_context
        context.update({
            'bulk_upload': {
                "help_site": {
                    "address": "https://dimagi.atlassian.net/wiki/spaces/commcarepublic/pages/2143946840/Multimedia+Manager#Option-3:-Multimedia-Manager---Bulk-Media-Upload",  # noqa: E501
                    "name": _("CommCare Help Site"),
                },
                "download_url": reverse(DownloadMultimediaZip.urlname, args=[self.domain, self.app.get_id]),
                "adjective": _("multimedia"),
                "plural_noun": _("multimedia files"),
                "action": reverse(ProcessBulkUploadView.urlname, args=[self.domain, self.app.get_id]),
            },
            'multimedia_state': self.app.check_media_state(),
        })
        context.update({
            'bulk_upload_form': get_bulk_upload_form(context),
        })
        return context


class BulkUploadMultimediaPollView(BaseMultimediaTemplateView):
    urlname = "hqmedia_bulk_upload_poll"

    def get(self, request, domain, app_id, processing_id):
        try:
            context = get_download_context(processing_id)
        except TaskFailedError:
            return HttpResponseServerError()
        status = BulkMultimediaStatusCache.get(processing_id)
        context.update(status.get_response())
        return render(request, 'hqmedia/partials/bulk_upload_status.html', context)


class BulkUploadMultimediaStatusView(BaseMultimediaTemplateView):
    urlname = "hqmedia_bulk_upload_status"
    page_title = gettext_noop('Bulk Upload Multimedia Status')
    template_name = "hqmedia/bulk_upload_status.html"

    def get(self, request, *args, **kwargs):
        context = self.get_context_data(**kwargs)
        context.update({
            'domain': self.domain,
            'download_id': kwargs['processing_id'],   # soil templates and js use "download_id"
            'poll_url': reverse(BulkUploadMultimediaPollView.urlname,
                                args=[self.domain, self.app.get_id, kwargs['processing_id']]),
            'title': _("Bulk Upload Multimedia Status"),
            'progress_text': _("Importing your multimedia. This may take some time..."),
            'error_text': _("Problem importing data! Please try again or report an issue."),
            'next_url': reverse(MultimediaReferencesView.urlname, args=[self.domain, self.app.get_id]),
            'next_url_text': _("Return to multimedia reference checker"),

        })
        return render(self.request, self.template_name, context)

    def page_url(self):
        return reverse(self.urlname, args=self.args, kwargs=self.kwargs)


@method_decorator(toggles.BULK_UPDATE_MULTIMEDIA_PATHS.required_decorator(), name='dispatch')
@method_decorator(require_can_edit_apps, name='dispatch')
class ManageMultimediaPathsView(BaseMultimediaTemplateView):
    urlname = "manage_multimedia_paths"
    template_name = "hqmedia/manage_paths.html"
    page_title = gettext_noop("Manage Multimedia Paths")

    @method_decorator(login_and_domain_required)
    @method_decorator(toggles.BULK_UPDATE_MULTIMEDIA_PATHS.required_decorator())
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)

    @property
    def parent_pages(self):
        return [{
            'title': _("Multimedia Reference Checker"),
            'url': reverse(MultimediaReferencesView.urlname, args=[self.domain, self.app.get_id]),
        }]

    @property
    def page_context(self):
        context = super().page_context
        context.update({
            'bulk_upload': {
                "download_url": reverse('download_multimedia_paths', args=[self.domain, self.app.get_id]),
                "adjective": _("multimedia paths"),
                "plural_noun": _("multimedia paths"),
                "help_link": "https://confluence.dimagi.com/display/ICDS/Multimedia+Path+Manager",
            },
        })
        context.update({
            'bulk_upload_form': get_bulk_upload_form(context),
        })
        return context

    def post(self, request, *args, **kwargs):
        handle = request.FILES['bulk_upload_file']
        extension = os.path.splitext(handle.name)[1][1:].strip().lower()
        if extension not in valid_extensions:
            messages.error(request, _("Please choose a file with one of the following extensions: "
                                      "{}").format(", ".join(valid_extensions)))
            return self.get(request, *args, **kwargs)

        meta = transient_file_store.write_file(handle, handle.name, self.domain)
        file_id = meta.identifier

        f = transient_file_store.get_tempfile_ref_for_contents(file_id)
        try:
            open_spreadsheet_download_ref(f)
        except SpreadsheetFileExtError:
            messages.error(request, _("File does not appear to be an Excel file. Please choose another file."))
            return self.get(request, *args, **kwargs)

        from corehq.apps.app_manager.views.media_utils import interpolate_media_path
        from corehq.apps.hqmedia.view_helpers import validate_multimedia_paths_rows, update_multimedia_paths

        # Get rows, filtering out header, no-ops, and any extra "Usages" columns
        rows = []
        with get_spreadsheet(f) as spreadsheet:
            for row in list(spreadsheet.iter_rows())[1:]:
                if row[1]:
                    rows.append(row[:2])

        (errors, warnings) = validate_multimedia_paths_rows(self.app, rows)
        if len(errors):
            for msg in errors:
                messages.error(request, msg, extra_tags='html')
            return self.get(request, *args, **kwargs)

        paths = {
            row[0]: interpolate_media_path(row[1]) for row in rows if row[1]
        }
        successes = update_multimedia_paths(self.app, paths)
        self.app.save()

        # Force all_media to reset
        self.app.all_media.reset_cache(self.app)
        self.app.all_media_paths.reset_cache(self.app)

        # Warn if any old paths remain in app (because they're used in a place this function doesn't know about)
        warnings = []
        self.app.remove_unused_mappings()
        app_paths = {m.path: True for m in self.app.all_media()}
        for old_path, new_path in paths.items():
            if old_path in app_paths:
                warnings.append(_("Could not completely update path <code>{}</code>, "
                                  "please check app for remaining references.").format(old_path))

        for msg in successes:
            messages.success(request, msg, extra_tags='html')
        for msg in warnings:
            messages.warning(request, msg, extra_tags='html')
        return self.get(request, *args, **kwargs)


@toggles.BULK_UPDATE_MULTIMEDIA_PATHS.required_decorator()
@require_can_edit_apps
@require_GET
def download_multimedia_paths(request, domain, app_id):
    from corehq.apps.hqmedia.view_helpers import download_multimedia_paths_rows
    app = get_app(domain, app_id)

    headers = ((_("Paths"), (_("Old Path"), _("New Path"), _("Usages"))),)
    rows = download_multimedia_paths_rows(app, only_missing=request.GET.get('only_missing', "false") == "true")

    temp = io.BytesIO()
    export_raw(headers, rows, temp)
    filename = '{app_name} v.{app_version} - App Multimedia Paths'.format(
        app_name=app.name,
        app_version=app.version)
    return export_response(temp, Format.XLS_2007, filename)


@method_decorator(toggles.BULK_UPDATE_MULTIMEDIA_PATHS.required_decorator(), name='dispatch')
@method_decorator(require_can_edit_apps, name='dispatch')
class MultimediaTranslationsCoverageView(BaseMultimediaTemplateView):
    urlname = "multimedia_translations_coverage"
    template_name = "hqmedia/translations_coverage.html"
    page_title = gettext_noop("Translations Coverage")

    @property
    def parent_pages(self):
        return [{
            'title': _("Multimedia Reference Checker"),
            'url': reverse(MultimediaReferencesView.urlname, args=[self.domain, self.app.get_id]),
        }]

    @property
    def page_context(self):
        context = super(MultimediaTranslationsCoverageView, self).page_context
        selected_build_id = self.request.POST.get('build_id')
        selected_build_text = ''
        if selected_build_id:
            build = get_app(self.app.domain, selected_build_id)
            selected_build_text = str(build.version)
            if build.build_comment:
                selected_build_text += ": " + build.build_comment
        context.update({
            "media_types": {t: CommCareMultimedia.get_doc_class(t).get_nice_name()
                            for t in CommCareMultimedia.get_doc_types()},
            "selected_langs": self.request.POST.getlist('langs', []),
            "selected_media_types": self.request.POST.getlist('media_types', ['CommCareAudio']),
            "selected_build_id": selected_build_id,
            "selected_build_text": selected_build_text,
        })
        return context

    def post(self, request, *args, **kwargs):
        error = False

        langs = request.POST.getlist('langs')
        if not langs:
            error = True
            messages.error(request, "Please select a language.")

        media_types = request.POST.getlist('media_types')
        if not media_types:
            error = True
            messages.error(request, "Please select a media type.")

        if not error:
            build_id = self.request.POST.get('build_id')
            build = get_app(self.app.domain, build_id) if build_id else self.app
            default_paths = build.all_media_paths(lang=build.default_language)
            default_paths = {p for p in default_paths
                             if p in build.multimedia_map
                             and build.multimedia_map[p].media_type in media_types}
            for lang in langs:
                fallbacks = default_paths.intersection(build.all_media_paths(lang=lang))
                if fallbacks:
                    messages.warning(request,
                                     "The following paths do not have references in <strong>{}</strong>:"
                                     "<ul>{}</ul>".format(lang,
                                                          "".join(["<li>{}</li>".format(f) for f in fallbacks])),
                                     extra_tags='html')
                else:
                    messages.success(request,
                                     "All paths checked have a <strong>{}</strong> reference.".format(lang),
                                     extra_tags='html')

        return self.get(request, *args, **kwargs)


@method_decorator(toggles.BULK_UPDATE_MULTIMEDIA_PATHS.required_decorator(), name='dispatch')
@method_decorator(require_can_edit_apps, name='dispatch')
class MultimediaAudioTranslatorFileView(BaseMultimediaTemplateView):
    urlname = "multimedia_audio_translator"
    template_name = "hqmedia/audio_translator.html"
    page_title = gettext_noop("Download Audio Translator Files")

    @property
    def parent_pages(self):
        return [{
            'title': _("Multimedia Reference Checker"),
            'url': reverse(MultimediaReferencesView.urlname, args=[self.domain, self.app.get_id]),
        }]

    def get(self, request, *args, **kwargs):
        lang = request.GET.get('lang')
        if lang:
            from corehq.apps.hqmedia.view_helpers import download_audio_translator_files
            eligible_for_transifex_only = request.GET.get('skip_blacklisted', "false") == "true"
            files = download_audio_translator_files(self.domain, self.app, lang, eligible_for_transifex_only)
            zip_in_memory = io.BytesIO()
            with zipfile.ZipFile(zip_in_memory, "w", zipfile.ZIP_DEFLATED) as zip_content:
                for filename, workbook in files.items():
                    zip_content.writestr(filename, get_file_content_from_workbook(workbook))
            today = datetime.strftime(datetime.utcnow(), "%Y-%m-%d")
            filename = "Audio Translator Files {} {}.zip".format(lang, today)
            zip_in_memory.seek(0)
            response = HttpResponse(zip_in_memory.read(), content_type='application/zip')
            response['Content-Disposition'] = 'attachment; filename="{}"'.format(filename)
            return response
        return super().get(request, *args, **kwargs)


class BaseProcessUploadedView(BaseMultimediaView):
    upload_filename = 'Filedata'

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
        return self.request.FILES.get(self.upload_filename)

    @property
    @memoized
    def mime_type(self):
        try:
            data = self.uploaded_file.file.read()
            return CommCareMultimedia.get_mime_type(data, filename=self.uploaded_file.name)
        except Exception as e:
            raise BadMediaFileException("There was an error fetching the MIME type of your file. Error: %s" % e)

    @method_decorator(require_permission(HqPermissions.edit_apps, login_decorator=login_and_domain_required))
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
            self.errors.append(str(e))
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
    upload_filename = "bulk_upload_file"

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
        if self.mime_type not in self.valid_mime_types():
            raise BadMediaFileException(_("Uploaded file is not a ZIP file."))
        if not self.uploaded_zip:
            raise BadMediaFileException(_("There is no ZIP file."))
        if self.uploaded_zip.testzip():
            raise BadMediaFileException(_("Unable to extract the ZIP file."))

    def process_upload(self):
        if hasattr(self.uploaded_file, 'temporary_file_path') and settings.SHARED_DRIVE_CONF.temp_dir:
            prefix = DownloadBase.new_id_prefix
            processing_id = prefix + uuid.uuid4().hex
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

    def post(self, request, *args, **kwargs):
        self.errors = []
        try:
            self.validate_file()
            response = self.process_upload()
        except BadMediaFileException as e:
            messages.error(request, str(e))
            return HttpResponseRedirect(
                reverse(BulkUploadMultimediaView.urlname, args=[self.domain, self.app.id])
            )
        return HttpResponseRedirect(
            reverse(
                BulkUploadMultimediaStatusView.urlname,
                args=[self.domain, self.app.id, response['processing_id']],
            )
        )

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
        if is_linked_app(self.app):
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
                if not isinstance(data, str):
                    yield os.path.join(folder), data
            except NameError as e:
                message = "%(path)s produced an ERROR: %(error)s" % {
                    'path': path,
                    'error': e,
                }
                errors.append(message)
    return _media_files(), errors


def iter_app_files(app, include_multimedia_files, include_index_files,
                   build_profile_id=None, download_targeted_version=False):
    file_iterator = []
    errors = []
    index_file_count = 0
    multimedia_file_count = 0
    if include_multimedia_files:
        media_objects = list(app.get_media_objects(build_profile_id=build_profile_id, remove_unused=True))
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
            domain=self.app.domain,
            app_id=self.app.id,
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
        return s.encode('utf-8') if isinstance(s, str) else s

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
        errors = [str(e)]

    return _files(files), errors, len(files)
