from __future__ import absolute_import
import json
from couchdbkit import ResourceNotFound
from django.http import (
    Http404,
    HttpResponseRedirect,
)

from django.urls import reverse
from django.views.generic import View
from django.contrib import messages
from django.utils.translation import ugettext as _, ugettext_lazy
from django.utils.decorators import method_decorator

from corehq.apps.domain.decorators import LoginAndDomainMixin
from corehq import toggles
from dimagi.utils.web import json_response
from dimagi.utils.decorators.memoized import memoized

from corehq.form_processor.exceptions import XFormNotFound
from corehq.apps.domain.views import (
    AddRepeaterView,
    BaseRepeaterView,
    AddFormRepeaterView,
)
from corehq.apps.hqwebapp.decorators import use_select2
from corehq.motech.repeaters.models import (
    RepeatRecord,
    Repeater,
)
from corehq.apps.domain.decorators import domain_admin_required
from corehq.util.xml_utils import indent_xml
from .forms import CaseRepeaterForm, SOAPCaseRepeaterForm, SOAPLocationRepeaterForm


class AddCaseRepeaterView(AddRepeaterView):
    urlname = 'add_case_repeater'
    repeater_form_class = CaseRepeaterForm

    @use_select2
    def dispatch(self, request, *args, **kwargs):
        return super(AddCaseRepeaterView, self).dispatch(request, *args, **kwargs)

    @property
    def page_url(self):
        return reverse(self.urlname, args=[self.domain])

    def set_repeater_attr(self, repeater, cleaned_data):
        repeater = super(AddCaseRepeaterView, self).set_repeater_attr(repeater, cleaned_data)
        repeater.white_listed_case_types = self.add_repeater_form.cleaned_data['white_listed_case_types']
        repeater.black_listed_users = self.add_repeater_form.cleaned_data['black_listed_users']
        return repeater


class AddCustomSOAPCaseRepeaterView(AddCaseRepeaterView):
    repeater_form_class = SOAPCaseRepeaterForm

    def make_repeater(self):
        repeater = super(AddCustomSOAPCaseRepeaterView, self).make_repeater()
        repeater.operation = self.add_repeater_form.cleaned_data['operation']
        return repeater


class AddCustomSOAPLocationRepaterView(AddRepeaterView):
    repeater_form_class = SOAPLocationRepeaterForm

    @property
    def page_url(self):
        return reverse(self.urlname, args=[self.domain])

    def make_repeater(self):
        repeater = super(AddCustomSOAPLocationRepaterView, self).make_repeater()
        repeater.operation = self.add_repeater_form.cleaned_data['operation']
        return repeater


class EditRepeaterView(BaseRepeaterView):
    urlname = 'edit_repeater'
    template_name = 'domain/admin/add_form_repeater.html'

    @property
    def repeater_id(self):
        return self.kwargs['repeater_id']

    @property
    def page_url(self):
        return reverse(self.urlname, args=[self.domain, self.repeater_type, self.repeater_id])

    @property
    @memoized
    def add_repeater_form(self):
        if self.request.method == 'POST':
            return self.repeater_form_class(
                self.request.POST,
                domain=self.domain,
                repeater_class=self.repeater_class
            )
        else:
            repeater_id = self.kwargs['repeater_id']
            repeater = Repeater.get(repeater_id)
            return self.repeater_form_class(
                domain=self.domain,
                repeater_class=self.repeater_class,
                data=repeater.to_json(),
                submit_btn_text=_("Update Repeater"),
            )

    @method_decorator(domain_admin_required)
    def dispatch(self, request, *args, **kwargs):
        if self.request.GET.get('repeater_type'):
            self.kwargs['repeater_type'] = self.request.GET['repeater_type']
        return super(EditRepeaterView, self).dispatch(request, *args, **kwargs)

    def initialize_repeater(self):
        return Repeater.get(self.kwargs['repeater_id'])

    def post_save(self, request, repeater):
        messages.success(request, _("Repeater Successfully Updated"))
        if self.request.GET.get('repeater_type'):
            return HttpResponseRedirect(
                (reverse(self.urlname, args=[self.domain, repeater.get_id]) +
                 '?repeater_type=' + self.kwargs['repeater_type'])
            )
        else:
            return HttpResponseRedirect(reverse(self.urlname, args=[self.domain, repeater.get_id]))


class EditCaseRepeaterView(EditRepeaterView, AddCaseRepeaterView):
    urlname = 'edit_case_repeater'
    page_title = ugettext_lazy("Edit Case Repeater")

    @property
    def page_url(self):
        return reverse(AddCaseRepeaterView.urlname, args=[self.domain])


class EditFormRepeaterView(EditRepeaterView, AddFormRepeaterView):
    urlname = 'edit_form_repeater'
    page_title = ugettext_lazy("Edit Form Repeater")

    @property
    def page_url(self):
        return reverse(AddFormRepeaterView.urlname, args=[self.domain])


class RepeatRecordView(LoginAndDomainMixin, View):

    urlname = 'repeat_record'
    http_method_names = ['get', 'post']

    @staticmethod
    def get_record_or_404(request, domain, record_id):
        try:
            record = RepeatRecord.get(record_id)
        except ResourceNotFound:
            raise Http404()

        if record.domain != domain:
            raise Http404()

        return record

    def get(self, request, domain):
        record_id = request.GET.get('record_id')
        record = self.get_record_or_404(request, domain, record_id)
        content_type = record.repeater.generator.content_type
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
        elif content_type == 'application/soap+xml':
            # we return a payload that is a dict, which is then converted to
            # XML by the zeep library before being sent along as a SOAP request.
            payload = json.dumps(payload, indent=4)

        return json_response({
            'payload': payload,
            'content_type': content_type,
        })

    def post(self, request, domain):
        # Retriggers a repeat record
        record_id = request.POST.get('record_id')
        record = self.get_record_or_404(request, domain, record_id)
        record.fire(force_send=True)
        return json_response({
            'success': record.succeeded,
            'failure_reason': record.failure_reason,
        })
