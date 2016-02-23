from django.core.urlresolvers import reverse
from django.views.generic import View

from dimagi.utils.web import json_response

from corehq.apps.domain.views import AddRepeaterView
from corehq.apps.style.decorators import use_select2
from corehq.apps.repeaters.models import RepeatRecord
from corehq.util.xml_utils import indent_xml
from .forms import CaseRepeaterForm


class AddCaseRepeaterView(AddRepeaterView):
    urlname = 'add_case_repeater'
    repeater_form_class = CaseRepeaterForm
    template_name = 'repeaters/add_case_repeater.html'

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


class RepeatRecordView(View):

    urlname = 'repeat_record'
    http_method_names = ['get', 'post']

    def get(self, request, domain):
        record = RepeatRecord.get(request.GET.get('record_id'))
        content_type = record.repeater.get_payload_generator(
            record.repeater.format_or_default_format()
        ).content_type
        payload = record.get_payload()
        if content_type == 'text/xml':
            payload = indent_xml(payload)

        return json_response({
            'payload': payload,
            'content_type': content_type,
        })

    def post(self, request, domain):
        # Retriggers a repeat record
        record = RepeatRecord.get(request.POST.get('record_id'))
        record.fire(max_tries=1, force_send=True)
        record.save()
        return json_response({
            'success': record.succeeded,
            'failure_reason': record.failure_reason,
        })
