import io
import itertools
import json
from collections import defaultdict

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db.models.query import Prefetch
from django.db.transaction import atomic
from django.http import HttpResponse, JsonResponse, HttpResponseRedirect
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.translation import ugettext_lazy as _
from django.views.generic import View

from couchexport.models import Format
from couchexport.writers import Excel2007ExportWriter

from corehq import toggles
from corehq.apps.case_importer.tracking.filestorage import make_temp_file
from corehq.apps.data_dictionary import util
from corehq.apps.data_dictionary.models import (
    PROPERTY_TYPE_CHOICES,
    CaseProperty,
    CasePropertyAllowedValue,
    CaseType,
)
from corehq.apps.data_dictionary.util import save_case_property
from corehq.apps.domain.decorators import login_and_domain_required
from corehq.apps.hqwebapp.decorators import use_jquery_ui
from corehq.apps.hqwebapp.utils import get_bulk_upload_form
from corehq.apps.settings.views import BaseProjectDataView
from corehq.motech.fhir.const import SUPPORTED_FHIR_RESOURCE_TYPES
from corehq.motech.fhir.utils import (
    load_fhir_resource_mappings,
    remove_fhir_resource_type,
    update_fhir_resource_type,
)
from corehq.project_limits.rate_limiter import (
    RateDefinition,
    RateLimiter,
    get_dynamic_rate_definition,
)
from corehq.util.files import file_extention_from_filename
from corehq.util.workbook_reading import open_any_workbook

FHIR_RESOURCE_TYPE_MAPPING_SHEET = "fhir_mapping"
ALLOWED_VALUES_SHEET_SUFFIX = "-vl"

data_dictionary_rebuild_rate_limiter = RateLimiter(
    feature_key='data_dictionary_rebuilds_per_user',
    get_rate_limits=lambda scope: get_dynamic_rate_definition(
        'data_dictionary_rebuilds_per_user',
        default=RateDefinition(
            per_hour=3,
            per_minute=2,
            per_second=1,
        )
    ).get_rate_limits(),
    scope_length=1,
)

@login_and_domain_required
@toggles.DATA_DICTIONARY.required_decorator()
def generate_data_dictionary(request, domain):
    if data_dictionary_rebuild_rate_limiter.allow_usage(domain):
        data_dictionary_rebuild_rate_limiter.report_usage(domain)
        try:
            util.generate_data_dictionary(domain)
        except util.OldExportsEnabledException:
            return JsonResponse({
                "failed": "Data Dictionary requires access to new exports"
            }, status=400)

        return JsonResponse({"status": "success"})
    else:
        return JsonResponse({
            "failed": "Rate limit exceeded. Please try again later."
        }, status=429)


@login_and_domain_required
@toggles.DATA_DICTIONARY.required_decorator()
def data_dictionary_json(request, domain, case_type_name=None):
    props = []
    fhir_resource_type_name_by_case_type = {}
    fhir_resource_prop_by_case_prop = {}
    queryset = CaseType.objects.filter(domain=domain).prefetch_related(
        Prefetch('properties', queryset=CaseProperty.objects.order_by('name')),
        Prefetch('properties__allowed_values', queryset=CasePropertyAllowedValue.objects.order_by('allowed_value'))
    )
    if toggles.FHIR_INTEGRATION.enabled(domain):
        fhir_resource_type_name_by_case_type, fhir_resource_prop_by_case_prop = load_fhir_resource_mappings(
            domain)
    if case_type_name:
        queryset = queryset.filter(name=case_type_name)
    for case_type in queryset:
        p = {
            "name": case_type.name,
            "fhir_resource_type": fhir_resource_type_name_by_case_type.get(case_type),
            "properties": [],
        }
        for prop in case_type.properties.all():
            p['properties'].append({
                "description": prop.description,
                "fhir_resource_prop_path": fhir_resource_prop_by_case_prop.get(prop),
                "name": prop.name,
                "data_type": prop.data_type,
                "group": prop.group,
                "deprecated": prop.deprecated,
                "allowed_values": {av.allowed_value: av.description for av in prop.allowed_values.all()},
            })
        props.append(p)
    return JsonResponse({'case_types': props})


@login_and_domain_required
@toggles.DATA_DICTIONARY.required_decorator()
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


# atomic decorator is a performance optimization for looped saves
# as per http://stackoverflow.com/questions/3395236/aggregating-saves-in-django#comment38715164_3397586
@atomic
@login_and_domain_required
@toggles.DATA_DICTIONARY.required_decorator()
def update_case_property(request, domain):
    fhir_resource_type_obj = None
    errors = []
    update_fhir_resources = toggles.FHIR_INTEGRATION.enabled(domain)
    property_list = json.loads(request.POST.get('properties'))

    if update_fhir_resources:
        errors, fhir_resource_type_obj = _update_fhir_resource_type(request, domain)
    if not errors:
        for property in property_list:
            case_type = property.get('caseType')
            name = property.get('name')
            description = property.get('description')
            data_type = property.get('data_type')
            group = property.get('group')
            deprecated = property.get('deprecated')
            allowed_values = property.get('allowed_values')
            if update_fhir_resources:
                fhir_resource_prop_path = property.get('fhir_resource_prop_path')
                remove_path = property.get('removeFHIRResourcePropertyPath', False)
            else:
                fhir_resource_prop_path, remove_path = None, None
            error = save_case_property(name, case_type, domain, data_type, description, group, deprecated,
                                       fhir_resource_prop_path, fhir_resource_type_obj, remove_path,
                                       allowed_values)
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
@toggles.DATA_DICTIONARY.required_decorator()
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
    case_prop_headers = [_('Case Property'), _('Group'), _('Data Type'), _('Description'), _('Deprecated')]
    allowed_value_headers = [_('Case Property'), _('Valid Value'), _('Valid Value Description')]

    case_type_data, case_prop_data = _generate_data_for_export(domain, export_fhir_data)

    outfile = io.BytesIO()
    writer = Excel2007ExportWriter()
    header_table = _get_headers_for_export(
        export_fhir_data, case_type_headers, case_prop_headers, case_prop_data, allowed_value_headers)
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
            _('Group'): case_prop.group,
            _('Data Type'): case_prop.data_type,
            _('Description'): case_prop.description,
            _('Deprecated'): case_prop.deprecated
        }
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
                            allowed_value_headers):
    header_table = []
    if export_fhir_data:
        header_table.append((FHIR_RESOURCE_TYPE_MAPPING_SHEET, [case_type_headers]))
        case_prop_headers.extend([_('FHIR Resource Property'), _('Remove Resource Property(Y)')])
    for tab_name in case_prop_data:
        header_table.append((tab_name, [case_prop_headers]))
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
    @method_decorator(toggles.DATA_DICTIONARY.required_decorator())
    def dispatch(self, request, *args, **kwargs):
        return super(DataDictionaryView, self).dispatch(request, *args, **kwargs)

    @property
    def main_context(self):
        main_context = super(DataDictionaryView, self).main_context
        fhir_integration_enabled = toggles.FHIR_INTEGRATION.enabled(self.domain)
        if fhir_integration_enabled:
            main_context.update({
                'fhir_resource_types': SUPPORTED_FHIR_RESOURCE_TYPES,
            })
        main_context.update({
            'question_types': [{'value': k, 'display': v} for k, v in PROPERTY_TYPE_CHOICES if k],
            'fhir_integration_enabled': fhir_integration_enabled,
        })
        return main_context


class UploadDataDictionaryView(BaseProjectDataView):
    page_title = _("Upload Data Dictionary")
    template_name = "hqwebapp/bulk_upload.html"
    urlname = 'upload_data_dict'

    @method_decorator(login_and_domain_required)
    @use_jquery_ui
    @method_decorator(toggles.DATA_DICTIONARY.required_decorator())
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
        errors = _process_bulk_upload(bulk_file, self.domain)
        if errors:
            messages.error(request, _("Errors in upload: {}").format(
                "<ul>{}</ul>".format("".join([f"<li>{e}</li>" for e in errors]))
            ), extra_tags="html")
        else:
            messages.success(request, _('Data dictionary import complete'))
        return self.get(request, *args, **kwargs)


def _process_bulk_upload(bulk_file, domain):
    filename = make_temp_file(bulk_file.read(), file_extention_from_filename(bulk_file.name))
    errors = []
    import_fhir_data = toggles.FHIR_INTEGRATION.enabled(domain)
    fhir_resource_type_by_case_type = {}
    expected_columns_in_prop_sheet = 5

    if import_fhir_data:
        expected_columns_in_prop_sheet = 7

    worksheets = []
    allowed_value_info = {}
    prop_row_info = {}
    seen_props = defaultdict(set)
    missing_valid_values = set()
    with open_any_workbook(filename) as workbook:
        for worksheet in workbook.worksheets:
            if worksheet.title.endswith(ALLOWED_VALUES_SHEET_SUFFIX):
                case_type = worksheet.title[:-len(ALLOWED_VALUES_SHEET_SUFFIX)]
                allowed_value_info[case_type] = defaultdict(dict)
                prop_row_info[case_type] = defaultdict(list)
                for (i, row) in enumerate(itertools.islice(worksheet.iter_rows(), 1, None), start=2):
                    if len(row) < 3:
                        errors.append(_('Expecting 3 columns, found only {}').format(len(row)))
                    else:
                        prop_name, allowed_value, description = [cell.value or '' for cell in row[0:3]]
                        if allowed_value and not prop_name:
                            msg_format = _('Error in valid values for case type {}, row {}: missing case property')
                            msg_val = msg_format.format(case_type, i)
                            errors.append(msg_val)
                        else:
                            allowed_value_info[case_type][prop_name][allowed_value] = description
                            prop_row_info[case_type][prop_name].append(i)
            else:
                worksheets.append(worksheet)

        for worksheet in worksheets:
            if worksheet.title == FHIR_RESOURCE_TYPE_MAPPING_SHEET:
                if import_fhir_data:
                    _errors, fhir_resource_type_by_case_type = _process_fhir_resource_type_mapping_sheet(
                        domain, worksheet)
                    errors.extend(_errors)
                continue
            case_type = worksheet.title
            for (i, row) in enumerate(itertools.islice(worksheet.iter_rows(), 1, None), start=2):
                if len(row) < expected_columns_in_prop_sheet:
                    error = _('Not enough columns')
                else:
                    error, fhir_resource_prop_path, fhir_resource_type, remove_path = None, None, None, None
                    name, group, data_type, description, deprecated = [cell.value for cell in row[:5]]
                    seen_props[case_type].add(name)
                    if import_fhir_data:
                        fhir_resource_prop_path, remove_path = row[5:]
                        remove_path = remove_path == 'Y' if remove_path else False
                        fhir_resource_type = fhir_resource_type_by_case_type.get(case_type)
                        if fhir_resource_prop_path and not fhir_resource_type:
                            error = _('Could not find resource type for {}').format(case_type)
                    if not error:
                        if case_type in allowed_value_info:
                            allowed_values = allowed_value_info[case_type][name]
                        else:
                            allowed_values = None
                            missing_valid_values.add(case_type)
                        error = save_case_property(name, case_type, domain, data_type, description, group,
                                                   deprecated, fhir_resource_prop_path, fhir_resource_type,
                                                   remove_path, allowed_values)
                if error:
                    errors.append(_('Error in case type {}, row {}: {}').format(case_type, i, error))

    for case_type in missing_valid_values:
        errors.append(_('Missing valid values sheet for case type {}').format(case_type))

    for case_type in allowed_value_info:
        for prop_name in allowed_value_info[case_type]:
            if prop_name not in seen_props[case_type]:
                msg_format = _(
                    'Error in valid values for case type {}, nonexistent property listed ({}), row(s): {}')
                msg_val = msg_format.format(
                    case_type, prop_name, ', '.join(str(v) for v in prop_row_info[case_type][prop_name]))
                errors.append(msg_val)

    return errors


def _process_fhir_resource_type_mapping_sheet(domain, worksheet):
    errors = []
    fhir_resource_type_by_case_type = {}
    for (i, row) in enumerate(itertools.islice(worksheet.iter_rows(), 1, None)):
        if len(row) < 3:
            errors.append(_('Not enough columns in {} sheet').format(FHIR_RESOURCE_TYPE_MAPPING_SHEET))
        else:
            case_type, fhir_resource_type, remove_resource_type = [cell.value for cell in row[:3]]
            remove_resource_type = remove_resource_type == 'Y' if remove_resource_type else False
            if remove_resource_type:
                remove_fhir_resource_type(domain, case_type)
                continue
            case_type_obj = CaseType.objects.get(domain=domain, name=case_type)
            try:
                fhir_resource_type_obj = update_fhir_resource_type(domain, case_type_obj, fhir_resource_type)
            except ValidationError as e:
                for key, msgs in dict(e).items():
                    for msg in msgs:
                        errors.append(_("FHIR Resource {} {}: {}").format(fhir_resource_type, key, msg))
            else:
                fhir_resource_type_by_case_type[case_type] = fhir_resource_type_obj
    return errors, fhir_resource_type_by_case_type
