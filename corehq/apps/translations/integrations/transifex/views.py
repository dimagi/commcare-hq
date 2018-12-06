from __future__ import absolute_import
from __future__ import unicode_literals

from io import open

import openpyxl
import polib
from corehq.apps.translations.integrations.transifex.transifex import Transifex
from corehq.apps.translations.integrations.transifex.utils import transifex_details_available_for_domain
from corehq.apps.translations.utils import get_file_content_from_workbook

from django.contrib import messages
from django.http import HttpResponse
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.translation import (
    ugettext as _,
    ugettext_noop,
    ugettext_lazy,
)
from memoized import memoized
from openpyxl import Workbook

from corehq import toggles
from corehq.apps.domain.views.base import BaseDomainView
from corehq.apps.hqwebapp.decorators import use_select2_v4
from corehq.apps.locations.permissions import location_safe
from corehq.apps.translations.forms import (
    ConvertTranslationsForm,
    PullResourceForm,
    AppTranslationsForm,
)
from corehq.apps.translations.generators import Translation, PoFileGenerator
from corehq.apps.translations.integrations.transifex.exceptions import ResourceMissing
from corehq.apps.translations.tasks import (
    push_translation_files_to_transifex,
    pull_translation_files_from_transifex,
    delete_resources_on_transifex,
)
from corehq.util.files import safe_filename_header


class BaseTranslationsView(BaseDomainView):
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
    section_name = ugettext_noop("Translations")

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
            _occurrence = row[occurrence].value if occurrence is not None else ''
            _context = row[context].value if context is not None else ''
            translations[worksheet.title].append(
                Translation(
                    row[source].value,
                    row[translation].value,
                    [(_occurrence, None)],
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
            with open(generated_files[0].path, 'r', encoding="utf-8") as f:
                return f.read()

    def _generate_excel_file(self):
        """
        extract translations from po file and converts to a xlsx file

        :return: Workbook object
        """
        uploaded_file = self.convert_translation_form.cleaned_data.get('upload_file')
        po_file = polib.pofile(uploaded_file.read())
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
        wb = self._generate_excel_file()
        content = get_file_content_from_workbook(wb)
        response = HttpResponse(content, content_type="text/html; charset=utf-8")
        response['Content-Disposition'] = safe_filename_header(self._uploaded_file_name.split('.po')[0], 'xlsx')
        return response

    def post(self, request, *args, **kwargs):
        if self.convert_translation_form.is_valid():
            uploaded_filename = self._uploaded_file_name
            if uploaded_filename.endswith('.xls') or uploaded_filename.endswith('.xlsx'):
                return self._po_file_response()
            elif uploaded_filename.endswith('.po'):
                return self._excel_file_response()
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
    section_name = ugettext_noop("Translations")

    @use_select2_v4
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

    def _generate_excel_file(self, domain, resource_slug):
        """
        extract translations from po file pulled from transifex and converts to a xlsx file

        :return: Workbook object
        """
        target_lang = self.pull_resource_form.cleaned_data['target_lang']
        transifex = Transifex(domain=domain, app_id=None,
                              source_lang=target_lang,
                              project_slug=self.pull_resource_form.cleaned_data['transifex_project_slug'],
                              version=None)
        wb = Workbook(write_only=True)
        ws = wb.create_sheet(title='translations')
        ws.append(['context', 'source', 'translation', 'occurrence'])
        for po_entry in transifex.client.get_translation(resource_slug, target_lang, False):
            ws.append([po_entry.msgctxt, po_entry.msgid, po_entry.msgstr,
                       po_entry.occurrences[0][0] if po_entry.occurrences else ''])
        return wb

    def _pull_resource(self, request):
        resource_slug = self.pull_resource_form.cleaned_data['resource_slug']
        wb = self._generate_excel_file(request.domain, resource_slug)
        content = get_file_content_from_workbook(wb)
        response = HttpResponse(content, content_type="text/html; charset=utf-8")
        response['Content-Disposition'] = safe_filename_header(resource_slug, 'xlsx')
        return response

    def post(self, request, *args, **kwargs):
        if self.transifex_integration_enabled(request):
            if self.pull_resource_form.is_valid():
                try:
                    return self._pull_resource(request)
                except ResourceMissing:
                    messages.add_message(request, messages.ERROR, 'Resource not found')
        return self.get(request, *args, **kwargs)


@location_safe
@method_decorator([toggles.APP_TRANSLATIONS_WITH_TRANSIFEX.required_decorator()], name='dispatch')
class AppTranslations(BaseTranslationsView):
    page_title = ugettext_lazy('App Translations')
    urlname = 'app_translations'
    template_name = 'app_translations.html'
    section_name = ugettext_lazy("Translations")

    @use_select2_v4
    def dispatch(self, request, *args, **kwargs):
        return super(AppTranslations, self).dispatch(request, *args, **kwargs)

    @property
    @memoized
    def translations_form(self):
        if self.request.POST:
            return AppTranslationsForm(self.domain, self.request.POST)
        else:
            return AppTranslationsForm(self.domain)

    @property
    def page_context(self):
        context = super(AppTranslations, self).page_context
        if context['transifex_details_available']:
            context['translations_form'] = self.translations_form
        return context

    def section_url(self):
        return reverse(ConvertTranslations.urlname, args=self.args, kwargs=self.kwargs)

    def transifex(self, domain, form_data):
        transifex_project_slug = form_data.get('transifex_project_slug')
        source_language_code = form_data.get('target_lang') or form_data.get('source_lang')
        return Transifex(domain, form_data['app_id'], source_language_code, transifex_project_slug,
                         form_data['version'],
                         use_version_postfix='yes' in form_data['use_version_postfix'],
                         update_resource='yes' in form_data['update_resource'])

    def perform_push_request(self, request, form_data):
        if form_data['target_lang']:
            if not self.ensure_resources_present(request):
                return False
        push_translation_files_to_transifex.delay(request.domain, form_data, request.user.email)
        messages.success(request, _('Successfully enqueued request to submit files for translations'))
        return True

    def resources_translated(self, request):
        resource_pending_translations = (self._transifex.
                                         resources_pending_translations(break_if_true=True))
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
            if self._transifex.resources_pending_translations(break_if_true=True, all_langs=True):
                messages.error(request, _('Resources yet to be completely translated for all languages. '
                                          'Hence, the request for locking resources can not be performed.'))
                return False
        pull_translation_files_from_transifex.delay(request.domain, form_data, request.user.email)
        messages.success(request, _('Successfully enqueued request to pull for translations. '
                                    'You should receive an email shortly'))
        return True

    def perform_delete_request(self, request, form_data):
        if not self.ensure_resources_present(request):
            return False
        if self._transifex.resources_pending_translations(break_if_true=True, all_langs=True):
            messages.error(request, _('Resources yet to be completely translated for all languages. '
                                      'Hence, the request for deleting resources can not be performed.'))
            return False
        delete_resources_on_transifex.delay(request.domain, form_data, request.user.email)
        messages.success(request, _('Successfully enqueued request to delete resources.'))
        return True

    def perform_request(self, request, form_data):
        self._transifex = self.transifex(request.domain, form_data)
        if not self._transifex.source_lang_is(form_data.get('source_lang')):
            messages.error(request, _('Source lang selected not available for the project'))
            return False
        else:
            if form_data['action'] == 'push':
                return self.perform_push_request(request, form_data)
            elif form_data['action'] == 'pull':
                return self.perform_pull_request(request, form_data)
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
                except ResourceMissing as e:
                    messages.error(request, e)
        return self.get(request, *args, **kwargs)
