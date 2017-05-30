
from django.http import JsonResponse
from django.utils.decorators import method_decorator
from django.views import View
from corehq.apps.domain.decorators import login_and_domain_required, LoginAndDomainMixin
from corehq.motech.repeaters.models import RepeatRecord
from corehq.motech.repeaters.views import AddCaseRepeaterView
from custom.infomovel_fgh.openmrs.repeater_helpers import Requests, \
    get_patient_identifier_types, get_person_attribute_types
from custom.infomovel_fgh.openmrs.repeaters import OpenmrsRepeater
from dimagi.utils.decorators.memoized import memoized


class OpenmrsRepeaterView(AddCaseRepeaterView):
    urlname = 'new_openmrs_repeater$'
    page_title = "Forward to OpenMRS"
    page_name = "Forward to OpenMRS"


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
    repeater = OpenmrsRepeater.get(repeater_id)
    assert repeater.domain == domain
    requests = Requests(repeater.url, repeater.username, repeater.password)
    raw_json = requests.get('/ws/rest/v1' + rest_uri, dict(request.GET)).json()
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
