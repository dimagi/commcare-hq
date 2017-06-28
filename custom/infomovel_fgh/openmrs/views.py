import json
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_http_methods
from corehq.apps.domain.decorators import login_and_domain_required
from corehq.motech.repeaters.models import RepeatRecord
from corehq.motech.repeaters.views import AddCaseRepeaterView
from custom.infomovel_fgh.openmrs.openmrs_config import OpenmrsCaseConfig, OpenmrsFormConfig
from custom.infomovel_fgh.openmrs.forms import OpenmrsConfigForm
from custom.infomovel_fgh.openmrs.repeater_helpers import Requests, \
    get_patient_identifier_types, get_person_attribute_types
from custom.infomovel_fgh.openmrs.repeaters import OpenmrsRepeater
from dimagi.utils.decorators.memoized import memoized


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
            repeater.openmrs_config.case_config = OpenmrsCaseConfig.wrap(data['case_config'])
            repeater.openmrs_config.form_configs = map(OpenmrsFormConfig.wrap, data['form_configs'])
            repeater.save()
            print repeater

    form = OpenmrsConfigForm(
        data={
            'form_configs': json.dumps([
                form_config.to_json()
                for form_config in repeater.openmrs_config.form_configs]),
            'case_config':  json.dumps(repeater.openmrs_config.case_config.to_json()),
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
    no_links = get_params.pop('nolinks', None) is not None
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
