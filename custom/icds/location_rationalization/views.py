from django.contrib import messages
from django.http import HttpResponse
from django.utils.decorators import method_decorator
from django.utils.functional import cached_property
from django.utils.translation import ugettext as _
from django.utils.translation import ugettext_noop

from memoized import memoized

from corehq import toggles
from corehq.apps.domain.views.base import BaseDomainView
from corehq.apps.locations.models import LocationType
from corehq.util.files import safe_filename_header
from corehq.util.workbook_json.excel import get_workbook
from custom.icds.location_rationalization.download import (
    RequestTemplateDownload,
)
from custom.icds.location_rationalization.dumper import Dumper
from custom.icds.location_rationalization.forms import (
    LocationRationalizationValidateForm,
    LocationRationalizationTemplateForm,
)
from custom.icds.location_rationalization.parser import Parser


@method_decorator([toggles.LOCATION_RATIONALIZATION.required_decorator()], name='dispatch')
class BaseLocationRationalizationView(BaseDomainView):
    section_name = ugettext_noop("Location Rationalization")

    @property
    def page_context(self):
        context = {}
        return context


class ValidateView(BaseLocationRationalizationView):
    page_title = _('Validate')
    urlname = 'validate_location_rationalization'
    template_name = 'location_rationalization/validate.html'

    def section_url(self):
        return self.page_url

    @property
    def page_context(self):
        context = super().page_context
        context['form'] = self.form
        return context

    @property
    @memoized
    def form(self):
        if self.request.POST:
            return LocationRationalizationValidateForm(self.request.POST, self.request.FILES,
                                                      location_types=self._location_types)
        return LocationRationalizationValidateForm()

    def post(self, request, *args, **kwargs):
        if self.form.is_valid():
            transitions, errors = self._parse_upload()
            [messages.error(request, error) for error in errors]
            if not errors:
                return self._generate_response(transitions)
        return self.get(request, *args, **kwargs)

    def _parse_upload(self):
        uploaded_file = self.form.cleaned_data.get('file')
        worksheet = get_workbook(uploaded_file).worksheets[0]
        return Parser(worksheet, self._location_types).parse()

    @cached_property
    def _location_types(self):
        location_types = [lt.code for lt in LocationType.objects.by_domain(self.domain)]
        location_types.reverse()
        return location_types

    def _generate_response(self, transitions):
        response_file = Dumper(self._location_types).dump(transitions)
        response_file.seek(0)
        response = HttpResponse(response_file, content_type="text/html; charset=utf-8")
        filename = self.form.cleaned_data['file'].name.split('.xlsx')[0] + '-Processed'
        response['Content-Disposition'] = safe_filename_header(filename, 'xlsx')
        return response


class DownloadTemplateView(BaseLocationRationalizationView):
    page_title = _('Download Template')
    urlname = 'download_location_rationalization_template'
    template_name = 'location_rationalization/download.html'

    def section_url(self):
        return self.page_url

    @property
    def page_context(self):
        context = super(DownloadTemplateView, self).page_context
        context['form'] = self.form
        return context

    @property
    @memoized
    def form(self):
        if self.request.POST:
            return LocationRationalizationTemplateForm(self.domain, self.request.POST)
        return LocationRationalizationTemplateForm(self.domain)

    def post(self, request, *args, **kwargs):
        if self.form.is_valid():
            return self._generate_response()
        return self.get(request, *args, **kwargs)

    def _generate_response(self):
        response_file = RequestTemplateDownload(
            self.domain, self.form.cleaned_data['location_id'],
            self.form.cleaned_data['location_type']).dump()
        response_file.seek(0)
        response = HttpResponse(response_file, content_type="text/html; charset=utf-8")
        filename = '%s Location Rationalization Request Template' % self.domain
        response['Content-Disposition'] = safe_filename_header(filename, 'xlsx')
        return response
