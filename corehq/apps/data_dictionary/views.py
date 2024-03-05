import io
import itertools
import json
from operator import attrgetter

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db.models.query import Prefetch
from django.db.transaction import atomic
from django.http import HttpResponse, HttpResponseRedirect, JsonResponse
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.translation import gettext_lazy as _
from django.views.generic import View

from couchexport.models import Format
from couchexport.writers import Excel2007ExportWriter

from corehq import toggles
from corehq.apps.data_dictionary.models import (
    CaseProperty,
    CasePropertyAllowedValue,
    CasePropertyGroup,
    CaseType,
)
from corehq.apps.data_dictionary.util import (
    save_case_property,
    save_case_property_group,
    delete_case_property,
    get_used_props_by_case_type,
    get_data_dict_props_by_case_type,
)
from corehq.apps.domain.decorators import login_and_domain_required
from corehq.apps.hqwebapp.decorators import use_jquery_ui
from corehq.apps.hqwebapp.utils import get_bulk_upload_form
from corehq.apps.settings.views import BaseProjectDataView
from corehq.apps.users.decorators import require_permission
from corehq.apps.users.models import HqPermissions
from corehq.motech.fhir.utils import (
    load_fhir_resource_mappings,
    load_fhir_resource_types,
    remove_fhir_resource_type,
    update_fhir_resource_type,
)
from corehq.apps.accounting.decorators import requires_privilege_with_fallback, requires_privilege
from corehq import privileges
from corehq.apps.app_manager.dbaccessors import get_case_type_app_module_count
from corehq.apps.geospatial.utils import get_geo_case_property

from .bulk import (
    process_bulk_upload,
    FHIR_RESOURCE_TYPE_MAPPING_SHEET,
    ALLOWED_VALUES_SHEET_SUFFIX,
)


@login_and_domain_required
@requires_privilege_with_fallback(privileges.DATA_DICTIONARY)
def data_dictionary_json(request, domain, case_type_name=None):
    props = []
    fhir_resource_type_name_by_case_type = {}
    fhir_resource_prop_by_case_prop = {}
    queryset = CaseType.objects.filter(domain=domain)
    if not request.GET.get('load_deprecated_case_types', False) == 'true':
        queryset = queryset.filter(is_deprecated=False)
    queryset = queryset.prefetch_related(
        Prefetch('groups', queryset=CasePropertyGroup.objects.order_by('index')),
        Prefetch('properties', queryset=CaseProperty.objects.order_by('group_id', 'index')),
        Prefetch('properties__allowed_values', queryset=CasePropertyAllowedValue.objects.order_by('allowed_value'))
    )
    if toggles.FHIR_INTEGRATION.enabled(domain):
        fhir_resource_type_name_by_case_type, fhir_resource_prop_by_case_prop = load_fhir_resource_mappings(
            domain)
    if case_type_name:
        queryset = queryset.filter(name=case_type_name)

    case_type_app_module_count = get_case_type_app_module_count(domain)
    data_validation_enabled = toggles.CASE_IMPORT_DATA_DICTIONARY_VALIDATION.enabled(domain)
    used_props_by_case_type = get_used_props_by_case_type(domain)
    geo_case_prop = get_geo_case_property(domain)
    for case_type in queryset:
        module_count = case_type_app_module_count.get(case_type.name, 0)
        used_props = used_props_by_case_type[case_type.name] if case_type.name in used_props_by_case_type else []
        p = {
            "name": case_type.name,
            "fhir_resource_type": fhir_resource_type_name_by_case_type.get(case_type),
            "groups": [],
            "is_deprecated": case_type.is_deprecated,
            "module_count": module_count,
            "properties": [],
            "is_safe_to_delete": len(used_props) == 0,
        }
        grouped_properties = {
            group: [
                {
                    'id': prop.id,
                    'description': prop.description,
                    'label': prop.label,
                    'fhir_resource_prop_path': fhir_resource_prop_by_case_prop.get(
                        prop
                    ),
                    'name': prop.name,
                    'deprecated': prop.deprecated,
                    'is_safe_to_delete': prop.name not in used_props and prop.name != geo_case_prop,
                }
                | (
                    {
                        'data_type': prop.data_type,
                        'allowed_values': {
                            av.allowed_value: av.description
                            for av in prop.allowed_values.all()
                        },
                    }
                    if data_validation_enabled
                    else {}
                )
                for prop in props
            ]
            for group, props in itertools.groupby(
                case_type.properties.all(), key=attrgetter('group_id')
            )
        }
        for group in case_type.groups.all():
            p["groups"].append({
                "id": group.id,
                "name": group.name,
                "description": group.description,
                "deprecated": group.deprecated,
                "properties": grouped_properties.get(group.id, [])
            })

        # Aggregate properties that dont have a group
        p["groups"].append({
            "name": "",
            "properties": grouped_properties.get(None, [])
        })
        props.append(p)
    return JsonResponse({
        'case_types': props,
        'geo_case_property': geo_case_prop,
    })


@login_and_domain_required
@requires_privilege_with_fallback(privileges.DATA_DICTIONARY)
@require_permission(HqPermissions.edit_data_dict)
def create_case_type(request, domain):
    name = request.POST.get("name")
    description = request.POST.get("description")
    if not name:
        messages.error(request, _("Case Type 'name' is required"))
        return redirect(DataDictionaryView.urlname, domain=domain)

    CaseType.objects.get_or_create(domain=domain, name=name, defaults={
        "description": description,
        "fully_generated": True
    })
    url = reverse(DataDictionaryView.urlname, args=[domain])
    return HttpResponseRedirect(f"{url}#{name}")


@login_and_domain_required
@requires_privilege_with_fallback(privileges.DATA_DICTIONARY)
@require_permission(HqPermissions.edit_data_dict)
def deprecate_or_restore_case_type(request, domain, case_type_name):
    is_deprecated = request.POST.get("is_deprecated") == 'true'
    case_type_obj = CaseType.objects.get(domain=domain, name=case_type_name)
    case_type_obj.is_deprecated = is_deprecated
    case_type_obj.save()

    CaseProperty.objects.filter(case_type=case_type_obj).update(deprecated=is_deprecated)
    CasePropertyGroup.objects.filter(case_type=case_type_obj).update(deprecated=is_deprecated)

    return JsonResponse({'status': 'success'})


@login_and_domain_required
@requires_privilege_with_fallback(privileges.DATA_DICTIONARY)
@require_permission(HqPermissions.edit_data_dict)
def delete_case_type(request, domain, case_type_name):
    try:
        case_type_obj = CaseType.objects.get(domain=domain, name=case_type_name)
        case_type_obj.delete()
    except CaseType.DoesNotExist:
        return JsonResponse({'status': 'failed'})
    return JsonResponse({'status': 'success'})


# atomic decorator is a performance optimization for looped saves
# as per http://stackoverflow.com/questions/3395236/aggregating-saves-in-django#comment38715164_3397586
@atomic
@login_and_domain_required
@requires_privilege_with_fallback(privileges.DATA_DICTIONARY)
@require_permission(HqPermissions.edit_data_dict)
def update_case_property(request, domain):
    fhir_resource_type_obj = None
    errors = []
    update_fhir_resources = toggles.FHIR_INTEGRATION.enabled(domain)
    property_list = json.loads(request.POST.get('properties'))
    group_list = json.loads(request.POST.get('groups'))
    data_validation_enabled = toggles.CASE_IMPORT_DATA_DICTIONARY_VALIDATION.enabled(domain)

    if update_fhir_resources:
        errors, fhir_resource_type_obj = _update_fhir_resource_type(request, domain)
    if not errors:
        for group in group_list:
            case_type = group.get("caseType")
            id = group.get("id")
            name = group.get("name")
            index = group.get("index")
            description = group.get("description")
            deprecated = group.get("deprecated")

            if name:
                error = save_case_property_group(id, name, case_type, domain, description, index, deprecated)

            if error:
                errors.append(error)

        for property in property_list:
            case_type = property.get('caseType')
            name = property.get('name')
            deleted = property.get('deleted')
            if deleted:
                error = delete_case_property(name, case_type, domain)
            else:
                label = property.get('label')
                index = property.get('index')
                description = property.get('description')
                data_type = property.get('data_type') if data_validation_enabled else None
                group = property.get('group')
                deprecated = property.get('deprecated')
                allowed_values = property.get('allowed_values') if data_validation_enabled else None
                if update_fhir_resources:
                    fhir_resource_prop_path = property.get('fhir_resource_prop_path')
                    remove_path = property.get('removeFHIRResourcePropertyPath', False)
                else:
                    fhir_resource_prop_path, remove_path = None, None
                error = save_case_property(name, case_type, domain, data_type, description, label, group,
                                           deprecated, fhir_resource_prop_path, fhir_resource_type_obj,
                                           remove_path, allowed_values, index)
            if error:
                errors.append(error)

    if errors:
        return JsonResponse({"status": "failed", "messages": errors}, status=400)
    else:
        return JsonResponse({"status": "success"})


def _update_fhir_resource_type(request, domain):
    errors, fhir_resource_type_obj = [], None
    fhir_resource_type = request.POST.get('fhir_resource_type')
    case_type = request.POST.get('case_type')
    if request.POST.get('remove_fhir_resource_type', '') == 'true':
        remove_fhir_resource_type(domain, case_type)
    elif fhir_resource_type and case_type:
        case_type_obj = CaseType.objects.get(domain=domain, name=case_type)
        try:
            fhir_resource_type_obj = update_fhir_resource_type(domain, case_type_obj, fhir_resource_type)
        except ValidationError as e:
            for key, msgs in dict(e).items():
                for msg in msgs:
                    errors.append(_("FHIR Resource {} {}: {}").format(fhir_resource_type, key, msg))
    return errors, fhir_resource_type_obj


@login_and_domain_required
@requires_privilege_with_fallback(privileges.DATA_DICTIONARY)
def update_case_property_description(request, domain):
    case_type = request.POST.get('caseType')
    name = request.POST.get('name')
    description = request.POST.get('description')
    error = save_case_property(name, case_type, domain, description=description)
    if error:
        return JsonResponse({"status": "failed", "errors": error}, status=400)
    else:
        return JsonResponse({"status": "success"})


def _export_data_dictionary(domain):
    export_fhir_data = toggles.FHIR_INTEGRATION.enabled(domain)
    case_type_headers = [_('Case Type'), _('FHIR Resource Type'), _('Remove Resource Type(Y)')]
    case_prop_headers = [
        _('Case Property'),
        _('Label'),
        _('Group'),
        _('Description'),
        _('Deprecated')
    ]
    if toggles.CASE_IMPORT_DATA_DICTIONARY_VALIDATION.enabled(domain):
        case_prop_headers.append(_('Data Type'))

    allowed_value_headers = [_('Case Property'), _('Valid Value'), _('Valid Value Description')]

    case_type_data, case_prop_data = _generate_data_for_export(domain, export_fhir_data)

    outfile = io.BytesIO()
    writer = Excel2007ExportWriter()
    header_table = _get_headers_for_export(
        export_fhir_data, case_type_headers, case_prop_headers, case_prop_data, allowed_value_headers, domain)
    writer.open(header_table=header_table, file=outfile)
    if export_fhir_data:
        _export_fhir_data(writer, case_type_headers, case_type_data)
    _export_case_prop_data(writer, case_prop_headers, case_prop_data, allowed_value_headers)
    writer.close()
    return outfile


def _generate_data_for_export(domain, export_fhir_data):
    def generate_prop_dict(case_prop, fhir_resource_prop):
        prop_dict = {
            _('Case Property'): case_prop.name,
            _('Label'): case_prop.label,
            _('Group'): case_prop.group_name,
            _('Description'): case_prop.description,
            _('Deprecated'): case_prop.deprecated
        }
        if toggles.CASE_IMPORT_DATA_DICTIONARY_VALIDATION.enabled(domain):
            prop_dict[_('Data Type')] = case_prop.get_data_type_display() if case_prop.data_type else ''
            if case_prop.data_type == 'select':
                prop_dict['allowed_values'] = [
                    {
                        _('Case Property'): case_prop.name,
                        _('Valid Value'): av.allowed_value,
                        _('Valid Value Description'): av.description,
                    } for av in case_prop.allowed_values.all()
                ]
        if export_fhir_data:
            prop_dict[_('FHIR Resource Property')] = fhir_resource_prop
        return prop_dict

    queryset = CaseType.objects.filter(domain=domain).prefetch_related(
        Prefetch('properties', queryset=CaseProperty.objects.order_by('name')),
        Prefetch('properties__allowed_values', queryset=CasePropertyAllowedValue.objects.order_by('allowed_value'))
    )
    case_type_data = {}
    case_prop_data = {}
    fhir_resource_prop_by_case_prop = {}

    if export_fhir_data:
        fhir_resource_type_name_by_case_type, fhir_resource_prop_by_case_prop = load_fhir_resource_mappings(
            domain
        )
        _add_fhir_resource_mapping_sheet(case_type_data, fhir_resource_type_name_by_case_type)

    for case_type in queryset:
        case_prop_data[case_type.name or _("No Name")] = [
            generate_prop_dict(prop, fhir_resource_prop_by_case_prop.get(prop))
            for prop in case_type.properties.all()
        ]
    return case_type_data, case_prop_data


def _add_fhir_resource_mapping_sheet(case_type_data, fhir_resource_type_name_by_case_type):
    case_type_data[FHIR_RESOURCE_TYPE_MAPPING_SHEET] = [
        {
            _('Case Type'): case_type.name,
            _('FHIR Resource Type'): fhir_resource_type,
            _('Remove Resource Type(Y)'): ''
        }
        for case_type, fhir_resource_type in fhir_resource_type_name_by_case_type.items()
    ]


def _get_headers_for_export(export_fhir_data, case_type_headers, case_prop_headers, case_prop_data,
                            allowed_value_headers, domain):
    data_validation_enabled = toggles.CASE_IMPORT_DATA_DICTIONARY_VALIDATION.enabled(domain)
    header_table = []
    if export_fhir_data:
        header_table.append((FHIR_RESOURCE_TYPE_MAPPING_SHEET, [case_type_headers]))
        case_prop_headers.extend([_('FHIR Resource Property'), _('Remove Resource Property(Y)')])
    for tab_name in case_prop_data:
        header_table.append((tab_name, [case_prop_headers]))
        if data_validation_enabled:
            header_table.append((f'{tab_name}{ALLOWED_VALUES_SHEET_SUFFIX}', [allowed_value_headers]))
    return header_table


def _export_fhir_data(writer, case_type_headers, case_type_data):
    rows = [
        [row.get(header, '') for header in case_type_headers]
        for row in case_type_data[FHIR_RESOURCE_TYPE_MAPPING_SHEET]
    ]
    writer.write([(FHIR_RESOURCE_TYPE_MAPPING_SHEET, rows)])


def _export_case_prop_data(writer, case_prop_headers, case_prop_data, allowed_value_headers):
    for tab_name, tab in case_prop_data.items():
        tab_rows = []
        allowed_values = []
        for row in tab:
            tab_rows.append([row.get(header, '') for header in case_prop_headers])
            if 'allowed_values' in row:
                allowed_values.extend(row['allowed_values'])
        writer.write([(tab_name, tab_rows)])
        tab_rows = []
        for row in allowed_values:
            tab_rows.append([row.get(header, '') for header in allowed_value_headers])
        writer.write([(f'{tab_name}{ALLOWED_VALUES_SHEET_SUFFIX}', tab_rows)])


class ExportDataDictionaryView(View):
    urlname = 'export_data_dictionary'

    @method_decorator(login_and_domain_required)
    def dispatch(self, request, *args, **kwargs):
        return super(ExportDataDictionaryView, self).dispatch(request, *args, **kwargs)

    def get(self, request, domain, *args, **kwargs):
        outfile = _export_data_dictionary(domain)
        response = HttpResponse(content_type=Format.from_format('xlsx').mimetype)
        response['Content-Disposition'] = 'attachment; filename="data_dictionary.xlsx"'
        response.write(outfile.getvalue())
        return response


class DataDictionaryView(BaseProjectDataView):
    page_title = _("Data Dictionary")
    template_name = "data_dictionary/base.html"
    urlname = 'data_dictionary'

    @method_decorator(login_and_domain_required)
    @use_jquery_ui
    @method_decorator(requires_privilege_with_fallback(privileges.DATA_DICTIONARY))
    @method_decorator(require_permission(HqPermissions.edit_data_dict,
                                         view_only_permission=HqPermissions.view_data_dict))
    def dispatch(self, request, *args, **kwargs):
        return super(DataDictionaryView, self).dispatch(request, *args, **kwargs)

    @property
    def main_context(self):
        main_context = super(DataDictionaryView, self).main_context
        fhir_integration_enabled = toggles.FHIR_INTEGRATION.enabled(self.domain)
        if fhir_integration_enabled:
            main_context.update({
                'fhir_resource_types': load_fhir_resource_types(),
            })
        main_context.update({
            'question_types': [{'value': t.value, 'display': t.label}
                               for t in CaseProperty.DataType
                               if t != CaseProperty.DataType.UNDEFINED],
            'fhir_integration_enabled': fhir_integration_enabled,
        })
        return main_context


class UploadDataDictionaryView(BaseProjectDataView):
    page_title = _("Upload Data Dictionary")
    template_name = "hqwebapp/bulk_upload.html"
    urlname = 'upload_data_dict'

    @method_decorator(login_and_domain_required)
    @use_jquery_ui
    @method_decorator(requires_privilege(privileges.DATA_DICTIONARY))
    @method_decorator(require_permission(HqPermissions.edit_data_dict))
    def dispatch(self, request, *args, **kwargs):
        return super(UploadDataDictionaryView, self).dispatch(request, *args, **kwargs)

    @property
    def parent_pages(self):
        return [{
            'title': DataDictionaryView.page_title,
            'url': reverse(DataDictionaryView.urlname, args=(self.domain,)),
        }]

    @property
    def page_context(self):
        main_context = super(UploadDataDictionaryView, self).main_context
        main_context.update({
            'bulk_upload': {
                "download_url": reverse('export_data_dictionary', args=[self.domain]),
                "adjective": _("data dictionary"),
                "plural_noun": _("data dictionary"),
            },
        })
        main_context.update({
            'bulk_upload_form': get_bulk_upload_form(main_context),
        })
        return main_context

    @method_decorator(atomic)
    def post(self, request, *args, **kwargs):
        bulk_file = self.request.FILES['bulk_upload_file']
        errors, warnings = process_bulk_upload(bulk_file, self.domain)
        if errors:
            messages.error(request, _("Errors in upload: {}").format(
                "<ul>{}</ul>".format("".join([f"<li>{e}</li>" for e in errors]))
            ), extra_tags="html")
        else:
            get_data_dict_props_by_case_type.clear(self.domain)
            messages.success(request, _('Data dictionary import complete'))
            if warnings:
                messages.warning(request, _("Warnings in upload: {}").format(
                    "<ul>{}</ul>".format("".join([f"<li>{e}</li>" for e in warnings]))
                ), extra_tags="html")
        return self.get(request, *args, **kwargs)
