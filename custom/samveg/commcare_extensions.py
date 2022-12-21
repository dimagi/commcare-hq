from corehq.apps.case_importer.extension_points import (
    custom_case_import_operations,
    custom_case_upload_file_operations,
)
from custom.samveg.case_importer.operations import AddCustomCaseProperties
from custom.samveg.case_importer.validators import (
    CallColumnsValidator,
    CallValidator,
    FormatValidator,
    RequiredColumnsValidator,
    RequiredValueValidator,
    UploadLimitValidator,
)
from custom.samveg.const import SAMVEG_DOMAINS

sheet_level_validations = [
    RequiredColumnsValidator,
    CallColumnsValidator,
]

row_level_validations = [
    RequiredValueValidator,
    CallValidator,
    FormatValidator,
    UploadLimitValidator,
]

additional_row_level_operations = [
    AddCustomCaseProperties,
]


@custom_case_upload_file_operations.extend(domains=SAMVEG_DOMAINS)
def samveg_case_upload_checks(domain, case_upload):
    errors = []
    with case_upload.get_spreadsheet() as spreadsheet:
        for validator in sheet_level_validations:
            errors.extend(validator.run(spreadsheet))
    return errors


@custom_case_import_operations.extend(domains=SAMVEG_DOMAINS)
def samveg_case_upload_row_operations(domain, row_num, raw_row, fields_to_update, import_context):
    all_errors = []
    for operation in row_level_validations:
        fields_to_update, errors = operation(
            row_num=row_num,
            raw_row=raw_row,
            fields_to_update=fields_to_update,
            import_context=import_context,
            domain=domain).run()
        all_errors.extend(errors)
    if not all_errors:
        for operation in additional_row_level_operations:
            fields_to_update, errors = operation(
                row_num=row_num,
                raw_row=raw_row,
                fields_to_update=fields_to_update,
                import_context=import_context,
                domain=domain).run()
            if errors:
                # add errors and break out to avoid calling more additional operations
                all_errors.extend(errors)
                break
    return fields_to_update, all_errors
