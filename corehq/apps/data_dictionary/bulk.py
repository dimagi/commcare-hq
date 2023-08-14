import itertools
from collections import defaultdict

from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError

from corehq import toggles
from corehq.apps.case_importer.tracking.filestorage import make_temp_file
from corehq.util.files import file_extention_from_filename
from corehq.util.workbook_reading import open_any_workbook
from corehq.motech.fhir.utils import (
    remove_fhir_resource_type,
    update_fhir_resource_type,
)

from .models import (
    CaseProperty,
    CaseType,
)
from .util import (
    save_case_property,
    get_column_headings,
    map_row_values_to_column_names,
)

FHIR_RESOURCE_TYPE_MAPPING_SHEET = "fhir_mapping"
ALLOWED_VALUES_SHEET_SUFFIX = "-vl"
COLUMN_MAPPING = {
    'case property': 'name',
    'label': 'label',
    'group': 'group',
    'data type': 'data_type_display',
    'description': 'description',
    'deprecated': 'deprecated',
}
COLUMN_MAPPING_VL = {
    'case property': 'prop_name',
    'valid value': 'allowed_value',
    'valid value description': 'description',
}
COLUMN_MAPPING_FHIR = {
    'case type': 'case_type',
    'fhir resource property': 'fhir_resource_type',
    'remove resource property(y)': 'remove_resource_type',
}
HEADER_ROW_INDEX = 1


def process_bulk_upload(bulk_file, domain):
    filename = make_temp_file(bulk_file.read(), file_extention_from_filename(bulk_file.name))
    errors = []
    allowed_value_info = {}
    prop_row_info = {}
    seen_props = defaultdict(set)

    with open_any_workbook(filename) as workbook:
        allowed_value_info, prop_row_info, error_list = _process_multichoice_sheets(
            workbook, allowed_value_info, prop_row_info)
        errors.extend(error_list)
        error_list, seen_props = _process_sheets(domain, workbook, allowed_value_info)
        errors.extend(error_list)

    error_list = _validate_values(allowed_value_info, seen_props, prop_row_info)
    errors.extend(error_list)

    return errors


def _process_multichoice_sheets(workbook, allowed_value_info, prop_row_info):
    errors = []
    for worksheet in workbook.worksheets:
        if not worksheet.title.endswith(ALLOWED_VALUES_SHEET_SUFFIX):
            continue

        case_type = worksheet.title[:-len(ALLOWED_VALUES_SHEET_SUFFIX)]
        allowed_value_info[case_type] = defaultdict(dict)
        prop_row_info[case_type] = defaultdict(list)
        column_headings = []
        for (i, row) in enumerate(itertools.islice(worksheet.iter_rows(), 0, None), start=1):
            if i == HEADER_ROW_INDEX:
                column_headings, heading_errors = get_column_headings(
                    row, valid_values=COLUMN_MAPPING_VL, sheet_name=worksheet.title, case_prop_name='prop_name')
                if len(heading_errors):
                    errors.extend(heading_errors)
                    break
                continue

            # Simply ignore any fully blank rows
            if len(row) < 1:
                continue

            row_vals = map_row_values_to_column_names(row, column_headings, default_val='')
            (allowed_value, prop_name, description) = (
                row_vals['allowed_value'], row_vals['prop_name'], row_vals['description'])

            if allowed_value and not prop_name:
                msg_format = _('Row {} in \"{}-vl\" sheet is missing a case property field')
                msg_val = msg_format.format(i, case_type)
                errors.append(msg_val)
            else:
                allowed_value_info[case_type][prop_name][allowed_value] = description
                prop_row_info[case_type][prop_name].append(i)

    return allowed_value_info, prop_row_info, errors


def _process_sheets(domain, workbook, allowed_value_info):
    import_fhir_data = toggles.FHIR_INTEGRATION.enabled(domain)
    fhir_resource_type_by_case_type = {}
    errors = []
    data_type_map = {t.label: t.value for t in CaseProperty.DataType}
    seen_props = defaultdict(set)
    missing_valid_values = set()

    for worksheet in workbook.worksheets:
        if worksheet.title.endswith(ALLOWED_VALUES_SHEET_SUFFIX):
            continue

        if worksheet.title == FHIR_RESOURCE_TYPE_MAPPING_SHEET:
            if import_fhir_data:
                _errors, fhir_resource_type_by_case_type = _process_fhir_resource_type_mapping_sheet(
                    domain, worksheet)
                errors.extend(_errors)
            continue
        case_type = worksheet.title

        column_headings = []
        for (i, row) in enumerate(itertools.islice(worksheet.iter_rows(), 0, None), start=1):
            if i == HEADER_ROW_INDEX:
                column_headings, heading_errors = get_column_headings(
                    row, valid_values=COLUMN_MAPPING, sheet_name=case_type, case_prop_name='name')
                if len(heading_errors):
                    errors.extend(heading_errors)
                    break
                continue

            # Simply ignore any fully blank rows
            if len(row) < 1:
                continue

            row_vals = map_row_values_to_column_names(row, column_headings)
            error, fhir_resource_prop_path, fhir_resource_type, remove_path = None, None, None, None
            (name, description, label, group, deprecated, data_type_display) = (
                row_vals['name'], row_vals['description'], row_vals['label'], row_vals['group'],
                row_vals['deprecated'], row_vals['data_type_display'])

            # Fall back to value from file if data_type_display is not found in the map.
            # This allows existing error path to report accurately the value that isn't found,
            # and also has a side-effect of allowing older files (pre change to export
            # display values) to import successfully.
            data_type = data_type_map.get(data_type_display, data_type_display)
            seen_props[case_type].add(name)
            if import_fhir_data:
                fhir_resource_prop_path, remove_path = row[5:]
                remove_path = remove_path.lower() == 'y' if remove_path else False
                fhir_resource_type = fhir_resource_type_by_case_type.get(case_type)
                if fhir_resource_prop_path and not fhir_resource_type:
                    error = _('Could not find resource type for {}').format(case_type)
            if not error:
                if case_type in allowed_value_info:
                    allowed_values = allowed_value_info[case_type][name]
                else:
                    allowed_values = None
                    missing_valid_values.add(case_type)
                error = save_case_property(name, case_type, domain, data_type, description,
                                           label, group, deprecated, fhir_resource_prop_path,
                                           fhir_resource_type, remove_path, allowed_values)
            if error:
                errors.append(_('Error in \"{}\" sheet, row {}: {}').format(case_type, i, error))

    for case_type in missing_valid_values:
        errors.append(_('Missing required valid \"{}-vl\" multi-choice sheet for case type \"{}\"').format(
            case_type, case_type))

    return errors, seen_props


def _process_fhir_resource_type_mapping_sheet(domain, worksheet):
    errors = []
    fhir_resource_type_by_case_type = {}
    for (i, row) in enumerate(itertools.islice(worksheet.iter_rows(), 0, None), start=1):
        if i == HEADER_ROW_INDEX:
            column_headings, heading_errors = get_column_headings(
                row, valid_values=COLUMN_MAPPING_FHIR, sheet_name=worksheet.title)
            if len(heading_errors):
                errors.extend(heading_errors)
                break
            continue

        if len(row) < 3:
            errors.append(_('Not enough columns in \"{}\" sheet').format(FHIR_RESOURCE_TYPE_MAPPING_SHEET))
        else:
            row_vals = map_row_values_to_column_names(row, column_headings)
            (case_type, remove_resource_type, fhir_resource_type) = (
                row_vals['case_type'], row_vals['remove_resource_type'], row_vals['fhir_resource_type'])

            remove_resource_type = remove_resource_type.lower() == 'y' if remove_resource_type else False
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


def _validate_values(allowed_value_info, seen_props, prop_row_info):
    errors = []
    for case_type in allowed_value_info:
        for prop_name in allowed_value_info[case_type]:
            if prop_name not in seen_props[case_type]:
                affected_rows = ', '.join(str(v) for v in prop_row_info[case_type][prop_name])
                msg_format = _(
                    'Case property \"{}\" referenced in \"{}-vl\" sheet that does not exist '
                    'in \"{}\" sheet. Row(s) affected: {}'
                )
                msg_val = msg_format.format(
                    prop_name, case_type, case_type, affected_rows
                )
                errors.append(msg_val)
    return errors
