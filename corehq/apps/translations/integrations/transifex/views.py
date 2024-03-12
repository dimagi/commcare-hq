from io import BytesIO, open
from zipfile import ZipFile

from django.contrib import messages
from django.http import HttpResponse
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy, gettext_noop

import openpyxl
import polib
from memoized import memoized

from corehq import toggles
from corehq.apps.domain.decorators import login_and_domain_required
from corehq.apps.domain.views.base import BaseDomainView
from corehq.apps.locations.permissions import location_safe
from corehq.apps.translations.forms import (
    AddTransifexBlacklistForm,
    AppTranslationsForm,
    ConvertTranslationsForm,
    DownloadAppTranslationsForm,
    MigrateTransifexProjectForm,
    PullResourceForm,
)
from corehq.apps.translations.generators import PoFileGenerator, Translation
from corehq.apps.translations.integrations.transifex.exceptions import TransifexApiException
from corehq.apps.translations.integrations.transifex.transifex import Transifex
from corehq.apps.translations.integrations.transifex.utils import (
    transifex_details_available_for_domain,
)
from corehq.apps.translations.models import TransifexBlacklist
from corehq.apps.translations.tasks import (
    backup_project_from_transifex,
    delete_resources_on_transifex,
    email_project_from_hq,
    migrate_project_on_transifex,
    pull_translation_files_from_transifex,
    push_translation_files_to_transifex,
)
from corehq.apps.translations.utils import get_file_content_from_workbook
from corehq.util.files import safe_filename_header


class BaseTranslationsView(BaseDomainView):
    section_name = gettext_noop("Translations")

    @property
    def page_context(self):
        context = {
            'transifex_details_available': self.transifex_details_available,
        }
        return context

    @property
    @memoized
    def transifex_details_available(self):
        return transifex_details_available_for_domain(self.domain)

    def transifex_integration_enabled(self, request):
        if not self.transifex_details_available:
            messages.error(request, _('Transifex integration not set for this domain'))
            return False
        return True


class ConvertTranslations(BaseTranslationsView):
    page_title = _('Convert Translations')
    urlname = 'convert_translations'
    template_name = 'convert_translations.html'

    @property
    @memoized
    def convert_translation_form(self):
        if self.request.POST:
            return ConvertTranslationsForm(self.request.POST, self.request.FILES)
        else:
            return ConvertTranslationsForm()

    @property
    @memoized
    def _uploaded_file_name(self):
        uploaded_file = self.convert_translation_form.cleaned_data.get('upload_file')
        return uploaded_file.name

    @staticmethod
    def _parse_excel_sheet(worksheet):
        """
        :return: the rows and the index for expected columns
        """
        rows = [row for row in worksheet.iter_rows()]
        headers = [cell.value for cell in rows[0]]
        source = headers.index('source')
        translation = headers.index('translation')
        occurrence = headers.index('occurrence') if 'occurrence' in headers else None
        context = headers.index('context') if 'context' in headers else None
        return rows, source, translation, occurrence, context

    def _generate_translations_for_po(self, worksheet):
        """
        :return: a list of Translation objects
        """
        rows, source, translation, occurrence, context = self._parse_excel_sheet(worksheet)
        translations = {worksheet.title: []}
        for row in rows[1:]:
            _occurrence = row[occurrence].value or '' if occurrence is not None else ''
            _context = row[context].value if context is not None else ''
            translations[worksheet.title].append(
                Translation(
                    row[source].value,
                    row[translation].value,
                    [(_occurrence, '')],
                    _context)
            )
        return translations

    def _generate_po_content(self, worksheet):
        """
        extract translations from worksheet and converts to a po file

        :return: content of file generated
        """
        translations = self._generate_translations_for_po(worksheet)
        with PoFileGenerator(translations, {}) as po_file_generator:
            generated_files = po_file_generator.generate_translation_files()
            with open(generated_files[0].path, 'rb') as f:
                return f.read()

    def _generate_excel_file(self, uploaded_file):
        """
        extract translations from po file and converts to a xlsx file

        :return: Workbook object
        """
        po_file = polib.pofile(uploaded_file.read().decode('utf-8'))
        wb = openpyxl.Workbook()
        ws = wb.worksheets[0]
        ws.title = "Translations"
        ws.append(['source', 'translation', 'context', 'occurrence'])
        for po_entry in po_file:
            ws.append([po_entry.msgid, po_entry.msgstr, po_entry.msgctxt,
                       po_entry.occurrences[0][0] if po_entry.occurrences else ''])
        return wb

    def _po_file_response(self):
        uploaded_file = self.convert_translation_form.cleaned_data.get('upload_file')
        worksheet = openpyxl.load_workbook(uploaded_file).worksheets[0]
        content = self._generate_po_content(worksheet)
        response = HttpResponse(content, content_type="text/html; charset=utf-8")
        response['Content-Disposition'] = safe_filename_header(worksheet.title, 'po')
        return response

    def _excel_file_response(self):
        wb = self._generate_excel_file(self.convert_translation_form.cleaned_data.get('upload_file'))
        content = get_file_content_from_workbook(wb)
        response = HttpResponse(content, content_type="text/html; charset=utf-8")
        response['Content-Disposition'] = safe_filename_header(self._uploaded_file_name.split('.po')[0], 'xlsx')
        return response

    def _zip_file_response(self):
        uploaded_file = self.convert_translation_form.cleaned_data.get('upload_file')
        uploaded_zipfile = ZipFile(uploaded_file)
        mem_file = BytesIO()
        with ZipFile(mem_file, 'w') as zipfile:
            for file_info in uploaded_zipfile.filelist:
                filename = file_info.filename
                if filename.endswith('.po'):
                    po_file = BytesIO(uploaded_zipfile.read(filename))
                    wb = self._generate_excel_file(po_file)
                    result_filename = filename.split('.po')[0]
                    zipfile.writestr(result_filename + '.xlsx', get_file_content_from_workbook(wb))
                elif filename.endswith('.xls') or filename.endswith('.xlsx'):
                    worksheet = openpyxl.load_workbook(BytesIO(uploaded_zipfile.read(filename))).worksheets[0]
                    po_file_content = self._generate_po_content(worksheet)
                    result_filename = filename.split('.xls')[0]
                    zipfile.writestr(result_filename + '.po', po_file_content)
                else:
                    assert False, "unexpected filename: {}".format(filename)
        mem_file.seek(0)
        response = HttpResponse(mem_file, content_type="text/html")
        zip_filename = 'Converted-' + uploaded_zipfile.filename.split('.zip')[0]
        response['Content-Disposition'] = safe_filename_header(zip_filename, "zip")
        return response

    def post(self, request, *args, **kwargs):
        if self.convert_translation_form.is_valid():
            uploaded_filename = self._uploaded_file_name
            if uploaded_filename.endswith('.xls') or uploaded_filename.endswith('.xlsx'):
                return self._po_file_response()
            elif uploaded_filename.endswith('.po'):
                return self._excel_file_response()
            elif uploaded_filename.endswith('.zip'):
                return self._zip_file_response()
        return self.get(request, *args, **kwargs)

    def section_url(self):
        return self.page_url

    @property
    def page_context(self):
        context = super(ConvertTranslations, self).page_context
        context['convert_translations_form'] = self.convert_translation_form
        return context


@method_decorator([toggles.APP_TRANSLATIONS_WITH_TRANSIFEX.required_decorator()], name='dispatch')
class PullResource(BaseTranslationsView):
    page_title = _('Pull Resource')
    urlname = 'pull_resource'
    template_name = 'pull_resource.html'

    def dispatch(self, request, *args, **kwargs):
        return super(PullResource, self).dispatch(request, *args, **kwargs)

    def section_url(self):
        return self.page_url

    @property
    @memoized
    def pull_resource_form(self):
        if self.request.POST:
            return PullResourceForm(self.domain, self.request.POST)
        else:
            return PullResourceForm(self.domain)

    @property
    def page_context(self):
        context = super(PullResource, self).page_context
        if context['transifex_details_available']:
            context['pull_resource_form'] = self.pull_resource_form
        return context

    def _generate_excel_file(self, domain, resource_slug, target_lang):
        """
        extract translations from po file pulled from transifex and converts to a xlsx file

        :return: Workbook object
        """
        transifex = Transifex(domain=domain, app_id=None,
                              source_lang=target_lang,
                              project_slug=self.pull_resource_form.cleaned_data['transifex_project_slug'],
                              version=None)
        wb = openpyxl.Workbook(write_only=True)
        ws = wb.create_sheet(title='translations')
        source_lang_col = transifex.lang_prefix + transifex.transifex_project_source_lang
        target_lang_col = transifex.lang_prefix + target_lang
        ws.append(['property', source_lang_col, target_lang_col, 'occurrence'])
        for po_entry in transifex.client.get_translation(resource_slug, target_lang, False):
            ws.append([po_entry.msgctxt, po_entry.msgid, po_entry.msgstr,
                       po_entry.occurrences[0][0] if po_entry.occurrences else ''])
        return wb

    @staticmethod
    def _generate_zip_file(transifex, target_lang):
        mem_file = BytesIO()
        with ZipFile(mem_file, 'w') as zipfile:
            for resource_slug in transifex.resource_slugs:
                wb = openpyxl.Workbook(write_only=True)
                ws = wb.create_sheet(title='translations')
                ws.append(['context', 'source', 'translation', 'occurrence'])
                for po_entry in transifex.client.get_translation(resource_slug, target_lang, False):
                    ws.append([po_entry.msgctxt, po_entry.msgid, po_entry.msgstr,
                               po_entry.occurrences[0][0] if po_entry.occurrences else ''])
                zipfile.writestr(resource_slug + '.xlsx', get_file_content_from_workbook(wb))
        mem_file.seek(0)
        return mem_file

    def _generate_response_file(self, domain, project_slug, resource_slug):
        """
        extract translations from po file(s) pulled from transifex and converts to a xlsx/zip file

        :return: Workbook object or BytesIO object
        """
        target_lang = self.pull_resource_form.cleaned_data['target_lang']
        transifex = Transifex(domain=domain, app_id=None,
                              source_lang=target_lang,
                              project_slug=project_slug)
        if resource_slug:
            return self._generate_excel_file(transifex, resource_slug, target_lang)
        else:
            return self._generate_zip_file(transifex, target_lang)

    def _pull_resource(self, request):
        resource_slug = self.pull_resource_form.cleaned_data['resource_slug']
        project_slug = self.pull_resource_form.cleaned_data['transifex_project_slug']
        file_response = self._generate_response_file(request.domain, project_slug, resource_slug)
        if isinstance(file_response, openpyxl.Workbook):
            content = get_file_content_from_workbook(file_response)
            response = HttpResponse(content, content_type="text/html; charset=utf-8")
            response['Content-Disposition'] = safe_filename_header(resource_slug, "xlsx")
        else:
            response = HttpResponse(file_response, content_type="text/html; charset=utf-8")
            response['Content-Disposition'] = safe_filename_header(project_slug, "zip")
        return response

    def post(self, request, *args, **kwargs):
        if self.transifex_integration_enabled(request):
            if self.pull_resource_form.is_valid():
                try:
                    return self._pull_resource(request)
                except TransifexApiException:
                    messages.add_message(request, messages.ERROR, 'Resource not found')
        return self.get(request, *args, **kwargs)


@method_decorator([toggles.APP_TRANSLATIONS_WITH_TRANSIFEX.required_decorator()], name='dispatch')
class BlacklistTranslations(BaseTranslationsView):
    page_title = _('Blacklist Translations')
    urlname = 'blacklist_translations'
    template_name = 'blacklist_translations.html'

    def section_url(self):
        return self.page_url

    @property
    def blacklist_form(self):
        if self.request.POST:
            return AddTransifexBlacklistForm(self.domain, self.request.POST)
        return AddTransifexBlacklistForm(self.domain)

    @property
    def page_context(self):
        context = super(BlacklistTranslations, self).page_context
        context['blacklisted_translations'] = TransifexBlacklist.translations_with_names(self.domain)
        context['blacklist_form'] = self.blacklist_form
        return context

    def post(self, request, *args, **kwargs):
        if self.transifex_integration_enabled(request):
            if self.blacklist_form.is_valid():
                self.blacklist_form.save()
        return self.get(request, *args, **kwargs)


@location_safe
@method_decorator([toggles.APP_TRANSLATIONS_WITH_TRANSIFEX.required_decorator()], name='dispatch')
class AppTranslations(BaseTranslationsView):
    page_title = gettext_lazy('App Translations')
    urlname = 'app_translations'
    template_name = 'app_translations.html'

    def dispatch(self, request, *args, **kwargs):
        return super(AppTranslations, self).dispatch(request, *args, **kwargs)

    @property
    @memoized
    def translations_form(self):
        form_action = self.request.POST.get('action')
        form_class = AppTranslationsForm.form_for(form_action)
        return form_class(self.domain, self.request.POST)

    @property
    def page_context(self):
        context = super(AppTranslations, self).page_context
        if context['transifex_details_available']:
            context['create_form'] = AppTranslationsForm.form_for('create')(self.domain)
            context['update_form'] = AppTranslationsForm.form_for('update')(self.domain)
            context['push_form'] = AppTranslationsForm.form_for('push')(self.domain)
            context['pull_form'] = AppTranslationsForm.form_for('pull')(self.domain)
            context['backup_form'] = AppTranslationsForm.form_for('backup')(self.domain)
            if self.request.user.is_staff:
                context['delete_form'] = AppTranslationsForm.form_for('delete')(self.domain)
        form_action = self.request.POST.get('action')
        if form_action:
            context[form_action + '_form'] = self.translations_form
        return context

    def section_url(self):
        return reverse(ConvertTranslations.urlname, args=self.args, kwargs=self.kwargs)

    def transifex(self, domain, form_data):
        transifex_project_slug = form_data.get('transifex_project_slug')
        source_language_code = form_data.get('target_lang') or form_data.get('source_lang')
        return Transifex(domain, form_data['app_id'], source_language_code, transifex_project_slug,
                         form_data['version'],
                         use_version_postfix='yes' in form_data['use_version_postfix'],
                         update_resource=(form_data['action'] == 'update'))

    def perform_push_request(self, request, form_data):
        if form_data['target_lang']:
            if not self.ensure_resources_present(request):
                return False
        push_translation_files_to_transifex.delay(request.domain, form_data, request.user.email)
        messages.success(request, _('Successfully enqueued request to submit files for translations'))
        return True

    def resources_translated(self, request):
        resource_pending_translations = (self._transifex.
                                         resources_pending_translations())
        if resource_pending_translations:
            messages.error(
                request,
                _("Resources yet to be completely translated, for ex: {}".format(
                    resource_pending_translations)))
            return False
        return True

    def ensure_resources_present(self, request):
        if not self._transifex.resource_slugs:
            messages.error(request, _('Resources not found for this project and version.'))
            return False
        return True

    def perform_pull_request(self, request, form_data):
        if not self.ensure_resources_present(request):
            return False
        if form_data['perform_translated_check']:
            if not self.resources_translated(request):
                return False
        if form_data['lock_translations']:
            if self._transifex.resources_pending_translations(all_langs=True):
                messages.error(request, _('Resources yet to be completely translated for all languages. '
                                          'Hence, the request for locking resources can not be performed.'))
                return False
        pull_translation_files_from_transifex.delay(request.domain, form_data, request.user.email)
        messages.success(request, _('Successfully enqueued request to pull for translations. '
                                    'You should receive an email shortly.'))
        return True

    def perform_backup_request(self, request, form_data):
        if not self.ensure_resources_present(request):
            return False
        backup_project_from_transifex.delay(request.domain, form_data, request.user.email)
        messages.success(request, _('Successfully enqueued request to take backup.'))
        return True

    def perform_delete_request(self, request, form_data):
        if not self.ensure_resources_present(request):
            return False
        if form_data['perform_translated_check']:
            if self._transifex.resources_pending_translations(all_langs=True):
                messages.error(request, _('Resources yet to be completely translated for all languages. '
                                          'Hence, the request for deleting resources can not be performed.'))
                return False
        delete_resources_on_transifex.delay(request.domain, form_data, request.user.email)
        messages.success(request, _('Successfully enqueued request to delete resources.'))
        return True

    def perform_request(self, request, form_data):
        self._transifex = self.transifex(request.domain, form_data)
        if form_data.get('source_lang') and not self._transifex.source_lang_is(form_data.get('source_lang')):
            messages.error(request, _('Source lang selected not available for the project'))
            return False
        else:
            if form_data['action'] in ['create', 'update', 'push']:
                return self.perform_push_request(request, form_data)
            elif form_data['action'] == 'pull':
                return self.perform_pull_request(request, form_data)
            elif form_data['action'] == 'backup':
                return self.perform_backup_request(request, form_data)
            elif form_data['action'] == 'delete':
                return self.perform_delete_request(request, form_data)

    def post(self, request, *args, **kwargs):
        if self.transifex_integration_enabled(request):
            form = self.translations_form
            if form.is_valid():
                form_data = form.cleaned_data
                try:
                    if self.perform_request(request, form_data):
                        return redirect(self.urlname, domain=self.domain)
                except TransifexApiException as e:
                    messages.error(request, e)
        return self.get(request, *args, **kwargs)


class DownloadTranslations(BaseTranslationsView):
    page_title = gettext_lazy('Download Translations')
    urlname = 'download_translations'
    template_name = 'download_translations.html'

    @property
    def page_context(self):
        context = super(DownloadTranslations, self).page_context
        if context['transifex_details_available']:
            context['download_form'] = DownloadAppTranslationsForm(self.domain)
        return context

    def section_url(self):
        return reverse(DownloadTranslations.urlname, args=self.args, kwargs=self.kwargs)

    def post(self, request, *args, **kwargs):
        if self.transifex_integration_enabled(request):
            form = DownloadAppTranslationsForm(self.domain, self.request.POST)
            if form.is_valid():
                form_data = form.cleaned_data
                email_project_from_hq.delay(request.domain, form_data, request.user.email)
                messages.success(request, _('Submitted request to download translations. '
                                            'You should receive an email shortly.'))
                return redirect(self.urlname, domain=self.domain)
        return self.get(request, *args, **kwargs)


@method_decorator([toggles.APP_TRANSLATIONS_WITH_TRANSIFEX.required_decorator()], name='dispatch')
class MigrateTransifexProject(BaseTranslationsView):
    page_title = gettext_lazy('Migrate Project')
    urlname = 'migrate_transifex_project'
    template_name = 'migrate_project.html'

    def section_url(self):
        return reverse(MigrateTransifexProject.urlname, args=self.args, kwargs=self.kwargs)

    @property
    @memoized
    def form(self):
        if self.request.POST:
            return MigrateTransifexProjectForm(self.domain, self.request.POST, self.request.FILES)
        else:
            return MigrateTransifexProjectForm(self.domain)

    @property
    def page_context(self):
        context = super(MigrateTransifexProject, self).page_context
        if context['transifex_details_available']:
            context['migration_form'] = self.form
        return context

    def _perform_request(self):
        migrator = self.form.migrator
        migrate_project_on_transifex.delay(
            migrator.domain,
            migrator.project_slug,
            migrator.source_app_id,
            migrator.target_app_id,
            self.form.uploaded_resource_id_mappings(),
            self.request.user.email
        )

    def post(self, request, *args, **kwargs):
        if self.transifex_integration_enabled(request):
            if self.form.is_valid():
                self._perform_request()
                messages.success(request, _('Submitted request to migrate project. '
                                            'You should receive an email shortly.'))
                return redirect(self.urlname, domain=self.domain)
        return self.get(request, *args, **kwargs)


@login_and_domain_required
def delete_translation_blacklist(request, domain, pk):
    TransifexBlacklist.objects.filter(domain=domain, pk=pk).delete()
    return redirect(BlacklistTranslations.urlname, domain=domain)
