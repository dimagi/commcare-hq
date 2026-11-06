import json

from django.core.exceptions import ValidationError
from django.core.serializers.json import DjangoJSONEncoder
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404
from django.utils.decorators import method_decorator
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy
from django.views.decorators.http import require_http_methods

from memoized import memoized

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


def parse_posted_importers(post_data):
    """
    Returns the list of importer dicts posted as JSON in
    ``openmrs_importers``. Raises ``ValidationError`` if the payload is
    missing or is not a list of objects.
    """
    try:
        importers = json.loads(post_data['openmrs_importers'])
    except KeyError:
        raise ValidationError(_('No OpenMRS Importers were submitted.'))
    except ValueError:
        raise ValidationError(_('OpenMRS Importers are not valid JSON.'))
    if not isinstance(importers, list) or not all(isinstance(i, dict) for i in importers):
        raise ValidationError(_('OpenMRS Importers must be a list of objects.'))
    return importers


def build_importer_forms(domain, posted_importers, current_importers):
    """
    Returns an ``OpenmrsImporterForm`` for each posted importer. Posted
    importers are paired with current importers by position; any beyond
    the current importers are new.
    """
    importer_forms = []
    for i, data in enumerate(posted_importers):
        if i < len(current_importers):
            importer = current_importers[i]
        else:
            importer = OpenmrsImporter(domain=domain)
        importer_forms.append(OpenmrsImporterForm(data, instance=importer))
    return importer_forms


def format_form_errors(forms):
    return '; '.join(
        f'{field}: {" ".join(messages)}'
        for form in forms
        for field, messages in form.errors.items()
    )


@method_decorator(use_bootstrap5, name='dispatch')
@method_decorator(require_permission(HqPermissions.edit_motech), name='dispatch')
@method_decorator(toggles.OPENMRS_INTEGRATION.required_decorator(), name='dispatch')
class OpenmrsImporterView(BaseProjectSettingsView):
    urlname = 'openmrs_importer_view'
    page_title = gettext_lazy("OpenMRS Importers")
    template_name = 'openmrs/importers.html'

    def post(self, request, *args, **kwargs):
        try:
            posted_importers = parse_posted_importers(request.POST)
        except ValidationError as err:
            return JsonResponse({'message': None, 'error': ' '.join(err.messages)}, status=400)
        current_importers = get_openmrs_importers_by_domain(request.domain)
        importer_forms = build_importer_forms(request.domain, posted_importers, current_importers)
        # Validate all importers before saving any of them
        invalid_forms = [form for form in importer_forms if not form.is_valid()]
        if invalid_forms:
            return JsonResponse(
                {'message': None, 'error': format_form_errors(invalid_forms)},
                status=400,
            )
        for form in importer_forms:
            form.save()
        for importer in current_importers[len(posted_importers):]:
            importer.delete()
        get_openmrs_importers_by_domain.clear(request.domain)
        return JsonResponse({'message': _('OpenMRS Importers saved'), 'error': None})

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
