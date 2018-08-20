from __future__ import absolute_import
from __future__ import unicode_literals
import openpyxl
import polib
import tempfile

from io import open
from memoized import memoized
from openpyxl import Workbook

from django.http import HttpResponse
from django.utils.translation import ugettext as _, ugettext_noop
from django.contrib import messages

from corehq.apps.translations.forms import (
    ConvertTranslationsForm,
    PullResourceForm,
)
from corehq.apps.app_manager.app_translations.generators import Translation, PoFileGenerator
from corehq.util.files import safe_filename_header
from corehq.apps.domain.views import BaseDomainView
from custom.icds.translations.integrations.exceptions import ResourceMissing
from custom.icds.translations.integrations.transifex import Transifex


class ConvertTranslations(BaseDomainView):
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
        rows = [row for row in worksheet.iter_rows()]
        headers = [cell.value for cell in rows[0]]
        source = headers.index('source')
        translation = headers.index('translation')
        occurrence = headers.index('occurrence') if 'occurrence' in headers else None
        context = headers.index('context') if 'context' in headers else None
        return rows, source, translation, occurrence, context

    def _generate_translations_for_po(self, worksheet):
        rows, source, translation, occurrence, context = self._parse_excel_sheet(worksheet)
        translations = {worksheet.title: []}
        for index, row in enumerate(rows[1:]):
            _occurrence = row[occurrence].value if occurrence else ''
            _context = row[context].value if context else ''
            translations[worksheet.title].append(
                Translation(
                    row[source].value,
                    row[translation].value,
                    [(_occurrence, None)],
                    _context)
            )
        return translations

    def _generate_po_file(self, worksheet):
        translations = self._generate_translations_for_po(worksheet)
        po_file_generator = PoFileGenerator()
        po_file_generator.generate_translation_files(translations, {})
        return po_file_generator

    def _generate_excel_file(self):
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
        po_file_generator = self._generate_po_file(worksheet)
        content = open(po_file_generator.generated_files[0][1], 'r', encoding="utf-8").read()
        response = HttpResponse(content, content_type="text/html; charset=utf-8")
        response['Content-Disposition'] = safe_filename_header(worksheet.title, 'po')
        return response

    def _excel_file_response(self):
        wb = self._generate_excel_file()
        with tempfile.TemporaryFile(suffix='.xlsx') as f:
            wb.save(f)
            f.seek(0)
            content = f.read()
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
        return {'convert_translations_form': self.convert_translation_form}


class PullResource(BaseDomainView):
    page_title = _('Pull Resource')
    urlname = 'pull_resource'
    template_name = 'pull_resource.html'
    section_name = ugettext_noop("Translations")

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
        return {'pull_resource_form': self.pull_resource_form}

    def _generate_excel_file(self, domain, resource_slug):
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
        with tempfile.TemporaryFile(suffix='.xlsx') as f:
            wb.save(f)
            f.seek(0)
            content = f.read()
        response = HttpResponse(content, content_type="text/html; charset=utf-8")
        response['Content-Disposition'] = safe_filename_header(resource_slug, 'xlsx')
        return response

    def post(self, request, *args, **kwargs):
        if self.pull_resource_form.is_valid():
            try:
                return self._pull_resource(request)
            except ResourceMissing:
                messages.add_message(request, messages.ERROR, 'Resource not found')
        return self.get(request, *args, **kwargs)
