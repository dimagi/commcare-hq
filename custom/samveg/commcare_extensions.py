from corehq.apps.case_importer.extension_points import custom_case_upload_file_checks
from custom.samveg.case_importer.validators import MandatoryColumnsValidator
from custom.samveg.const import SAMVEG_DOMAINS

validators = [
    MandatoryColumnsValidator,
]



@custom_case_upload_file_checks.extend(domains=SAMVEG_DOMAINS)
def samveg_case_upload_checks(domain, case_upload):
    errors = []
    with case_upload.get_spreadsheet() as spreadsheet:
        for validator in validators:
            if hasattr(validator, 'validate'):
                errors.extend(getattr(validator, 'validate')(spreadsheet))
    return errors
