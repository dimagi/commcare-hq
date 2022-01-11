from corehq.apps.case_importer.extension_points import (
    custom_case_import_operations,
    custom_case_upload_file_operations,
)
from custom.samveg.case_importer.validators import (
    CallValidator,
    MandatoryColumnsValidator,
    MandatoryValueValidator,
    UploadLimitValidator,
)
from custom.samveg.const import SAMVEG_DOMAINS

validators = [
    MandatoryColumnsValidator,
]


row_level_operations = [
    MandatoryValueValidator,
    CallValidator,
    UploadLimitValidator,
]


@custom_case_upload_file_operations.extend(domains=SAMVEG_DOMAINS)
def samveg_case_upload_checks(domain, case_upload):
    errors = []
    with case_upload.get_spreadsheet() as spreadsheet:
        for validator in validators:
            errors.extend(getattr(validator, 'run')(spreadsheet))
    return errors


@custom_case_import_operations.extend(domains=SAMVEG_DOMAINS)
def samveg_case_upload_row_operations(domain, row_num, raw_row, fields_to_update, import_context):
    all_errors = []
    for operation in row_level_operations:
        if hasattr(operation, 'run'):
            fields_to_update, errors = getattr(operation, 'run')(row_num, raw_row, fields_to_update,
                                                                 import_context=import_context)
            all_errors.extend(errors)
    return fields_to_update, all_errors
