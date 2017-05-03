import json

from django.http import HttpResponseRedirect
from django.urls import reverse
from django.views.generic import View
from django.contrib import messages
from django.utils.translation import ugettext as _, ugettext_lazy
from dimagi.utils.web import json_response
from dimagi.utils.decorators.memoized import memoized
from django.utils.decorators import method_decorator

from corehq.apps.domain.decorators import domain_admin_required
from corehq.form_processor.exceptions import XFormNotFound
from corehq.apps.domain.views import AddRepeaterView, AddFormRepeaterView, BaseRepeaterView
from corehq.apps.style.decorators import use_select2
from corehq.apps.repeaters.models import RepeatRecord, Repeater
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

    def set_repeater_attr(self, repeater, cleaned_data):
        repeater = super(AddCaseRepeaterView, self).set_repeater_attr(repeater, cleaned_data)
        repeater.white_listed_case_types = self.add_repeater_form.cleaned_data['white_listed_case_types']
        repeater.black_listed_users = self.add_repeater_form.cleaned_data['black_listed_users']
        return repeater


class EditRepeaterView(BaseRepeaterView):
    urlname = 'edit_repeater'
    template_name = 'domain/admin/add_form_repeater.html'

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
    template_name = 'repeaters/add_case_repeater.html'

    @property
    def page_url(self):
        return reverse(AddCaseRepeaterView.urlname, args=[self.domain])


class EditFormRepeaterView(EditRepeaterView, AddFormRepeaterView):
    urlname = 'edit_form_repeater'
    page_title = ugettext_lazy("Edit Form Repeater")

    @property
    def page_url(self):
        return reverse(AddFormRepeaterView.urlname, args=[self.domain])


class RepeatRecordView(View):

    urlname = 'repeat_record'
    http_method_names = ['get', 'post']

    def get(self, request, domain):
        record = RepeatRecord.get(request.GET.get('record_id'))
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
        record = RepeatRecord.get(request.POST.get('record_id'))
        record.fire(force_send=True)
        return json_response({
            'success': record.succeeded,
            'failure_reason': record.failure_reason,
        })
