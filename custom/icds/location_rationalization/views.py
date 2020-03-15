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
from custom.icds.location_rationalization.dumper import Dumper
from custom.icds.location_rationalization.forms import (
    LocationRationalizationRequestForm,
)
from custom.icds.location_rationalization.parser import Parser


@method_decorator([toggles.LOCATION_RATIONALIZATION.required_decorator()], name='dispatch')
class BaseLocationRationalizationView(BaseDomainView):
    section_name = ugettext_noop("Location Rationalization")

    @property
    def page_context(self):
        context = {}
        return context


class ValidateRequestView(BaseLocationRationalizationView):
    page_title = _('Validate')
    urlname = 'validate_location_rationalization_request'
    template_name = 'location_rationalization/request.html'

    def section_url(self):
        return self.page_url

    @property
    def page_context(self):
        context = super(ValidateRequestView, self).page_context
        context['form'] = self.form
        return context

    @property
    @memoized
    def form(self):
        if self.request.POST:
            return LocationRationalizationRequestForm(self.request.POST, self.request.FILES,
                                                      location_types=self._location_types)
        else:
            return LocationRationalizationRequestForm()

    def post(self, request, *args, **kwargs):
        if self.form.is_valid():
            transitions, errors = self._parse_upload()
            [messages.error(request, error) for error in errors]
            if not errors:
                return self._generate_response(transitions)
        return self.get(request, *args, **kwargs)

    def _parse_upload(self):
        uploaded_file = self.form.cleaned_data.get('file')
        ws = get_workbook(uploaded_file).worksheets[0]
        return Parser(ws, self._location_types).parse()

    @cached_property
    def _location_types(self):
        return list(LocationType.objects.filter(domain=self.domain).values_list('code', flat=True))

    def _generate_response(self, transitions):
        response_file = Dumper(self._location_types).dump(transitions)
        response_file.seek(0)
        response = HttpResponse(response_file, content_type="text/html; charset=utf-8")
        filename = self.form.cleaned_data['file'].name.split('.xlsx')[0] + '-Processed'
        response['Content-Disposition'] = safe_filename_header(filename, 'xlsx')
        return response
