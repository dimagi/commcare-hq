from __future__ import absolute_import
from __future__ import unicode_literals
import json

from django.core.serializers.json import DjangoJSONEncoder
from django.http import JsonResponse
from django.shortcuts import render
from django.utils.decorators import method_decorator
from django.utils.translation import ugettext_lazy, ugettext as _
from django.views.decorators.http import require_http_methods

from corehq import toggles
from corehq.apps.domain.decorators import login_and_domain_required
from corehq.apps.domain.views.settings import BaseProjectSettingsView
from corehq.apps.users.decorators import require_permission
from corehq.apps.users.models import Permissions
from corehq.motech.const import PASSWORD_PLACEHOLDER
from corehq.motech.openmrs.dbaccessors import get_openmrs_importers_by_domain
from corehq.motech.openmrs.models import OpenmrsImporter
from corehq.motech.openmrs.tasks import import_patients_to_domain
from corehq.motech.repeaters.models import RepeatRecord
from corehq.motech.openmrs.openmrs_config import OpenmrsCaseConfig, OpenmrsFormConfig
from corehq.motech.openmrs.forms import OpenmrsConfigForm, OpenmrsImporterForm
from corehq.motech.openmrs.models import ColumnMapping
from corehq.motech.openmrs.repeater_helpers import (
    get_patient_identifier_types,
    get_person_attribute_types,
)
from corehq.motech.requests import Requests
from corehq.motech.openmrs.repeaters import OpenmrsRepeater
from corehq.motech.utils import b64_aes_encrypt
from memoized import memoized
from dimagi.utils.web import json_response
from six.moves import map
from six.moves import range


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
    raw_json = get_patient_identifier_types(helper.repeater.requests)
    return JsonResponse(_filter_out_links(raw_json))


@login_and_domain_required
def openmrs_person_attribute_types(request, domain, repeater_id):
    helper = OpenmrsModelListViewHelper(request, domain, repeater_id)
    raw_json = get_person_attribute_types(helper.repeater.requests)
    return JsonResponse(_filter_out_links(raw_json))


@login_and_domain_required
def openmrs_raw_api(request, domain, repeater_id, rest_uri):
    get_params = dict(request.GET)
    no_links = get_params.pop('links', None) is None
    repeater = OpenmrsRepeater.get(repeater_id)
    assert repeater.domain == domain
    raw_json = repeater.requests.get('/ws/rest/v1' + rest_uri, get_params).json()
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

    def _update_importer(self, importer, data):
        for key, value in data.items():
            if key == 'password' and value != PASSWORD_PLACEHOLDER:
                value = b64_aes_encrypt(value)
            elif key == 'report_params':
                value = json.loads(value)
            elif key == 'column_map':
                list_of_dicts = json.loads(value)
                value = [ColumnMapping(**d) for d in list_of_dicts]
            setattr(importer, key, value)
        importer.save()

    def post(self, request, *args, **kwargs):
        try:
            new_openmrs_importers = json.loads(request.POST['openmrs_importers'])
            current_openmrs_importers = get_openmrs_importers_by_domain(request.domain)
            i = -1
            for i, openmrs_importer in enumerate(current_openmrs_importers):
                if i < len(new_openmrs_importers):
                    self._update_importer(openmrs_importer, new_openmrs_importers[i])
                else:
                    # Delete removed OpenMRS Importers
                    openmrs_importer.delete()
            if i + 1 < len(new_openmrs_importers):
                # Insert new OpenMRS Importers
                for j in range(i + 1, len(new_openmrs_importers)):
                    openmrs_importer = OpenmrsImporter(domain=request.domain)
                    self._update_importer(openmrs_importer, new_openmrs_importers[j])
            get_openmrs_importers_by_domain.clear(request.domain)
            return json_response({'message': _('OpenMRS Importers saved'), 'error': None})
        except Exception as err:
            return json_response({'message': None, 'error': str(err)}, status_code=500)

    @property
    def page_context(self):
        # TODO: Look up locations for location_id field.

        openmrs_importers = []
        for importer in get_openmrs_importers_by_domain(self.request.domain):
            dict_ = dict(importer)
            dict_['password'] = PASSWORD_PLACEHOLDER
            dict_['report_params'] = json.dumps(dict_['report_params'], cls=DjangoJSONEncoder, indent=2)
            dict_['column_map'] = json.dumps([
                {k: v for k, v in dict(m).items() if not (
                    # Drop '"doc_type": ColumnMapping' from each column mapping.
                    k == 'doc_type' or
                    # Drop "data_type" if it's not specified
                    (k == 'data_type' and v is None)
                )}
                for m in dict_['column_map']
            ], indent=2)
            openmrs_importers.append(dict_)
        return {
            'openmrs_importers': openmrs_importers,
            'form': OpenmrsImporterForm(),  # Use an unbound form to render openmrs_importer_template.html
        }
