from corehq.apps.case_importer.extension_points import (
    custom_case_upload_file_operations,
)
from custom.samveg.case_importer.validators import MandatoryColumnsValidator
from custom.samveg.const import SAMVEG_DOMAINS

validators = [
    MandatoryColumnsValidator,
]


@custom_case_upload_file_operations.extend(domains=SAMVEG_DOMAINS)
def samveg_case_upload_checks(domain, case_upload):
    errors = []
    with case_upload.get_spreadsheet() as spreadsheet:
        for validator in validators:
            errors.extend(getattr(validator, 'run')(spreadsheet))
    return errors
