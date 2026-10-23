import json

from django.core.serializers.json import DjangoJSONEncoder
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404
from django.utils.decorators import method_decorator
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy
from django.views.decorators.http import require_http_methods

from memoized import memoized

from dimagi.utils.web import json_response

from corehq import privileges, toggles
from corehq.apps.accounting.decorators import requires_privilege_with_fallback
from corehq.apps.domain.views.settings import BaseProjectSettingsView
from corehq.apps.hqwebapp.decorators import use_bootstrap5
from corehq.apps.users.decorators import require_permission
from corehq.apps.users.models import HqPermissions
from corehq.motech.const import PASSWORD_PLACEHOLDER
from corehq.motech.openmrs.dbaccessors import get_openmrs_importers_by_domain
from corehq.motech.openmrs.forms import (
    OpenmrsConfigForm,
    OpenmrsImporterForm,
    OpenmrsRepeaterForm,
)
from corehq.motech.openmrs.models import OpenmrsImporter
from corehq.motech.openmrs.openmrs_config import (
    OpenmrsCaseConfig,
    OpenmrsFormConfig,
)
from corehq.motech.openmrs.repeater_helpers import (
    get_patient_identifier_types,
    get_person_attribute_types,
)
from corehq.motech.openmrs.repeaters import OpenmrsRepeater
from corehq.motech.openmrs.tasks import import_patients_to_domain
from corehq.motech.repeaters.models import RepeatRecord
from corehq.motech.repeaters.views import AddCaseRepeaterView, EditRepeaterView


def require_openmrs_repeater_access(view_func):
    """
    Restricts OpenMRS repeater views to users who can edit MOTECH
    integrations, on projects with Data Forwarding and the OpenMRS
    integration enabled.
    """
    view_func = toggles.OPENMRS_INTEGRATION.required_decorator()(view_func)
    view_func = requires_privilege_with_fallback(privileges.DATA_FORWARDING)(view_func)
    return require_permission(HqPermissions.edit_motech)(view_func)


@use_bootstrap5
@require_openmrs_repeater_access
@require_http_methods(["GET", "POST"])
def config_openmrs_repeater(request, domain, repeater_id):
    helper = OpenmrsModelListViewHelper(request, domain, repeater_id)
    repeater = helper.repeater

    if request.method == 'POST':
        form = OpenmrsConfigForm(data=request.POST)
        if form.is_valid():
            data = form.cleaned_data
            repeater.openmrs_config['openmrs_provider'] = data['openmrs_provider']
            # wrapping for schema validation
            repeater.openmrs_config['case_config'] = OpenmrsCaseConfig.wrap(data['patient_config']).to_json()
            repeater.openmrs_config['form_configs'] = [
                OpenmrsFormConfig.wrap(enc).to_json()
                for enc in data['encounters_config']
            ]
            repeater.save()

    else:
        form = OpenmrsConfigForm(
            data={
                'openmrs_provider': repeater.openmrs_config['openmrs_provider'],
                'encounters_config': json.dumps(repeater.openmrs_config['form_configs']),
                'patient_config': json.dumps(repeater.openmrs_config['case_config']),
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
        return get_object_or_404(
            OpenmrsRepeater,
            id=self.repeater_id,
            domain=self.domain,
        )


def _filter_out_links(json):
    if isinstance(json, dict):
        return {key: _filter_out_links(value) for key, value in json.items() if key != 'links'}
    elif isinstance(json, list):
        return [_filter_out_links(value) for value in json]
    else:
        return json


@require_openmrs_repeater_access
def openmrs_patient_identifier_types(request, domain, repeater_id):
    helper = OpenmrsModelListViewHelper(request, domain, repeater_id)
    raw_json = get_patient_identifier_types(helper.repeater.requests)
    return JsonResponse(_filter_out_links(raw_json))


@require_openmrs_repeater_access
def openmrs_person_attribute_types(request, domain, repeater_id):
    helper = OpenmrsModelListViewHelper(request, domain, repeater_id)
    raw_json = get_person_attribute_types(helper.repeater.requests)
    return JsonResponse(_filter_out_links(raw_json))


@require_openmrs_repeater_access
def openmrs_raw_api(request, domain, repeater_id, rest_uri):
    get_params = dict(request.GET)
    no_links = get_params.pop('links', None) is None
    repeater = get_object_or_404(OpenmrsRepeater, id=repeater_id, domain=domain)
    raw_json = repeater.requests.get('/ws/rest/v1' + rest_uri, get_params).json()
    if no_links:
        return JsonResponse(_filter_out_links(raw_json))
    return JsonResponse(raw_json)


@require_openmrs_repeater_access
@require_http_methods(['POST'])
def openmrs_test_fire(request, domain, repeater_id, record_id):
    repeater = get_object_or_404(
        OpenmrsRepeater,
        domain=domain,
        id=repeater_id,
    )
    record = get_object_or_404(
        RepeatRecord,
        domain=domain,
        id=record_id,
        repeater_id=repeater.id,
    )
    repeater.fire_for_record(record)
    return JsonResponse({'status': 'OK'}, status=200)


@require_permission(HqPermissions.edit_motech)
@toggles.OPENMRS_INTEGRATION.required_decorator()
@require_http_methods(['POST'])
def openmrs_import_now(request, domain):
    import_patients_to_domain(request.domain, force=True)
    return JsonResponse({'status': 'Accepted'}, status=202)


@method_decorator(use_bootstrap5, name='dispatch')
@method_decorator(require_permission(HqPermissions.edit_motech), name='dispatch')
@method_decorator(toggles.OPENMRS_INTEGRATION.required_decorator(), name='dispatch')
class OpenmrsImporterView(BaseProjectSettingsView):
    urlname = 'openmrs_importer_view'
    page_title = gettext_lazy("OpenMRS Importers")
    template_name = 'openmrs/importers.html'

    def post(self, request, *args, **kwargs):
        try:
            new_openmrs_importers = json.loads(request.POST['openmrs_importers'])
            current_openmrs_importers = get_openmrs_importers_by_domain(request.domain)
            forms = []
            for i, data in enumerate(new_openmrs_importers):
                if i < len(current_openmrs_importers):
                    importer = current_openmrs_importers[i]
                else:
                    importer = OpenmrsImporter(domain=request.domain)
                forms.append(OpenmrsImporterForm(data, instance=importer))
            # Validate all importers before saving any of them
            invalid = [form for form in forms if not form.is_valid()]
            if invalid:
                errors = '; '.join(
                    f'{field}: {" ".join(messages)}'
                    for form in invalid
                    for field, messages in form.errors.items()
                )
                return json_response({'message': None, 'error': errors}, status_code=400)
            for form in forms:
                form.save()
            # Delete removed OpenMRS Importers
            for importer in current_openmrs_importers[len(new_openmrs_importers):]:
                importer.delete()
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
                    k == 'doc_type'
                    # Drop "data_type" if it's not specified
                    or (k == 'data_type' and v is None)
                )}
                for m in dict_['column_map']
            ], indent=2)
            openmrs_importers.append(dict_)
        return {
            'openmrs_importers': openmrs_importers,
            'form': OpenmrsImporterForm(),  # Use an unbound form to render openmrs_importer_template.html
        }


class AddOpenmrsRepeaterView(AddCaseRepeaterView):
    urlname = 'new_openmrs_repeater$'
    repeater_form_class = OpenmrsRepeaterForm
    page_title = gettext_lazy("Forward to OpenMRS")
    page_name = gettext_lazy("Forward to OpenMRS")

    def set_repeater_attr(self, repeater, cleaned_data):
        repeater = super().set_repeater_attr(repeater, cleaned_data)
        repeater.location_id = (self.add_repeater_form
                                .cleaned_data['location_id'])
        repeater.atom_feed_enabled = (self.add_repeater_form
                                      .cleaned_data['atom_feed_enabled'])
        return repeater


class EditOpenmrsRepeaterView(EditRepeaterView, AddOpenmrsRepeaterView):
    urlname = 'edit_openmrs_repeater'
    page_title = gettext_lazy("Edit OpenMRS Repeater")
