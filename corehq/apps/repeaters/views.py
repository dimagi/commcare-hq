import json
from couchdbkit import ResourceNotFound
from django.http import Http404

from django.urls import reverse
from django.views.generic import View
from corehq.apps.domain.decorators import LoginAndDomainMixin

from dimagi.utils.web import json_response

from corehq.form_processor.exceptions import XFormNotFound
from corehq.apps.domain.views import AddRepeaterView
from corehq.apps.style.decorators import use_select2
from corehq.apps.repeaters.models import RepeatRecord
from corehq.util.xml_utils import indent_xml
from .forms import CaseRepeaterForm


class AddCaseRepeaterView(AddRepeaterView):
    urlname = 'add_case_repeater'
    repeater_form_class = CaseRepeaterForm
    template_name = 'domain/admin/add_form_repeater.html'

    @use_select2
    def dispatch(self, request, *args, **kwargs):
        return super(AddCaseRepeaterView, self).dispatch(request, *args, **kwargs)

    @property
    def page_url(self):
        return reverse(self.urlname, args=[self.domain])

    def make_repeater(self):
        repeater = super(AddCaseRepeaterView, self).make_repeater()
        repeater.white_listed_case_types = self.add_repeater_form.cleaned_data['white_listed_case_types']
        repeater.black_listed_users = self.add_repeater_form.cleaned_data['black_listed_users']
        return repeater


class UserRepeaterView(AddRepeaterView):
    urlname = "user_repeater"
    page_title = "Users"
    page_name = page_title

    @property
    def page_url(self):
        return reverse(self.urlname, args=[self.domain])


class LocationRepeaterView(AddRepeaterView):
    urlname = "location_repeater"
    page_title = "Locations"
    page_name = page_title

    @property
    def page_url(self):
        return reverse(self.urlname, args=[self.domain])


class RepeatRecordView(LoginAndDomainMixin, View):

    urlname = 'repeat_record'
    http_method_names = ['get', 'post']

    @staticmethod
    def get_record_or_404(request, domain):
        try:
            record = RepeatRecord.get(request.GET.get('record_id'))
        except ResourceNotFound:
            raise Http404()

        if record.domain != domain:
            raise Http404()

        return record

    def get(self, request, domain):
        record = self.get_record_or_404(request, domain)
        content_type = record.repeater.get_payload_generator(
            record.repeater.format_or_default_format()
        ).content_type
        try:
            payload = record.get_payload()
        except XFormNotFound:
            return json_response({
                'error': u'Odd, could not find payload for: {}'.format(record.payload_id)
            }, status_code=404)

        if content_type == 'text/xml':
            payload = indent_xml(payload)
        elif content_type == 'application/json':
            payload = json.dumps(json.loads(payload), indent=4)

        return json_response({
            'payload': payload,
            'content_type': content_type,
        })

    def post(self, request, domain):
        # Retriggers a repeat record
        record = self.get_record_or_404(request, domain)
        record.fire(force_send=True)
        return json_response({
            'success': record.succeeded,
            'failure_reason': record.failure_reason,
        })
