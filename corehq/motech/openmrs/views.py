from __future__ import absolute_import
import json
from django.http import JsonResponse, HttpResponseRedirect
from django.shortcuts import render
from django.utils.decorators import method_decorator
from django.utils.translation import ugettext_lazy
from django.views.decorators.http import require_http_methods
from corehq import toggles
from corehq.apps.domain.decorators import login_and_domain_required
from corehq.apps.domain.views import BaseProjectSettingsView
from corehq.apps.users.decorators import require_permission
from corehq.apps.users.models import Permissions
from corehq.motech.openmrs.dbaccessors import get_openmrs_importers_by_domain
from corehq.motech.openmrs.tasks import import_patients_to_domain
from corehq.motech.repeaters.models import RepeatRecord
from corehq.motech.repeaters.views import AddCaseRepeaterView
from corehq.motech.openmrs.openmrs_config import OpenmrsCaseConfig, OpenmrsFormConfig
from corehq.motech.openmrs.forms import OpenmrsConfigForm, OpenmrsImporterForm
from corehq.motech.openmrs.repeater_helpers import (
    Requests,
    get_patient_identifier_types,
    get_person_attribute_types,
)
from corehq.motech.openmrs.repeaters import OpenmrsRepeater
from dimagi.utils.decorators.memoized import memoized
from six.moves import map


class OpenmrsRepeaterView(AddCaseRepeaterView):
    urlname = 'new_openmrs_repeater$'
    page_title = "Forward to OpenMRS"
    page_name = "Forward to OpenMRS"


@login_and_domain_required
@require_http_methods(["GET", "POST"])
def openmrs_edit_config(request, domain, repeater_id):
    helper = OpenmrsModelListViewHelper(request, domain, repeater_id)
    repeater = helper.repeater

    if request.method == 'POST':
        form = OpenmrsConfigForm(data=request.POST)
        if form.is_valid():
            data = form.cleaned_data
            repeater.openmrs_config.openmrs_provider = data['openmrs_provider']
            repeater.openmrs_config.case_config = OpenmrsCaseConfig.wrap(data['case_config'])
            repeater.openmrs_config.form_configs = list(map(OpenmrsFormConfig.wrap, data['form_configs']))
            repeater.save()

    else:
        form = OpenmrsConfigForm(
            data={
                'openmrs_provider': repeater.openmrs_config.openmrs_provider,
                'form_configs': json.dumps([
                    form_config.to_json()
                    for form_config in repeater.openmrs_config.form_configs]),
                'case_config': json.dumps(repeater.openmrs_config.case_config.to_json()),
            }
        )
    return render(request, 'openmrs/edit_config.html', {
        'domain': domain,
        'repeater_id': repeater_id,
        'form': form
    })


class OpenmrsModelListViewHelper(object):
    def __init__(self, request, domain, repeater_id):
        self.domain = domain
        self.repeater_id = repeater_id

    @property
    @memoized
    def repeater(self):
        repeater = OpenmrsRepeater.get(self.repeater_id)
        assert repeater.domain == self.domain
        return repeater

    @property
    @memoized
    def requests(self):
        return Requests(self.repeater.url, self.repeater.username, self.repeater.password)


def _filter_out_links(json):
    if isinstance(json, dict):
        return {key: _filter_out_links(value) for key, value in json.items() if key != 'links'}
    elif isinstance(json, list):
        return [_filter_out_links(value) for value in json]
    else:
        return json


@login_and_domain_required
def openmrs_patient_identifier_types(request, domain, repeater_id):
    helper = OpenmrsModelListViewHelper(request, domain, repeater_id)
    raw_json = get_patient_identifier_types(helper.requests)
    return JsonResponse(_filter_out_links(raw_json))


@login_and_domain_required
def openmrs_person_attribute_types(request, domain, repeater_id):
    helper = OpenmrsModelListViewHelper(request, domain, repeater_id)
    raw_json = get_person_attribute_types(helper.requests)
    return JsonResponse(_filter_out_links(raw_json))


@login_and_domain_required
def openmrs_raw_api(request, domain, repeater_id, rest_uri):
    get_params = dict(request.GET)
    no_links = get_params.pop('links', None) is None
    repeater = OpenmrsRepeater.get(repeater_id)
    assert repeater.domain == domain
    requests = Requests(repeater.url, repeater.username, repeater.password)
    raw_json = requests.get('/ws/rest/v1' + rest_uri, get_params).json()
    if no_links:
        return JsonResponse(_filter_out_links(raw_json))
    return JsonResponse(raw_json)


@login_and_domain_required
def openmrs_test_fire(request, domain, repeater_id, record_id):
    repeater = OpenmrsRepeater.get(repeater_id)
    record = RepeatRecord.get(record_id)
    assert repeater.domain == domain
    assert record.domain == domain
    assert record.repeater_id == repeater.get_id

    attempt = repeater.fire_for_record(record)
    return JsonResponse(attempt.to_json())


@login_and_domain_required
@require_http_methods(['POST'])
def openmrs_import_now(request, domain):
    import_patients_to_domain.delay(request.domain, True)
    return JsonResponse({'status': 'Accepted'}, status=202)


@method_decorator(require_permission(Permissions.edit_motech), name='dispatch')
@method_decorator(toggles.OPENMRS_INTEGRATION.required_decorator(), name='dispatch')
class OpenmrsImporterView(BaseProjectSettingsView):
    urlname = 'openmrs_importer_view'
    page_title = ugettext_lazy("OpenMRS Importers")
    template_name = 'openmrs/importers.html'

    def post(self, request, *args, **kwargs):
        form = self.openmrs_importer_form
        if form.is_valid():
            form.save(self.domain)
            get_openmrs_importers_by_domain.clear(request.domain)
            return HttpResponseRedirect(self.page_url)
        context = self.get_context_data(**kwargs)
        return self.render_to_response(context)

    @property
    @memoized
    def openmrs_importer_form(self):
        importers = get_openmrs_importers_by_domain(self.request.domain)
        if importers:
            initial = dict(importers[0])  # TODO: Support multiple
            initial['column_map'] = [{k: v for k, v in dict(m).items() if k != 'doc_type'}  # Just for the pretty
                                     for m in initial['column_map']]
        else:
            initial = {}
        if self.request.method == 'POST':
            return OpenmrsImporterForm(self.request.POST, initial=initial)
        return OpenmrsImporterForm(initial=initial)

    @property
    def page_context(self):
        return {'openmrs_importer_form': self.openmrs_importer_form}
