from typing import List

from corehq.extensions import extension_point, ResultFormat


@extension_point(result_format=ResultFormat.FLATTEN)
def custom_case_upload_file_operations(domain, case_upload) -> List[str]:
    """Perform additional operations on a case upload file.

    Parameters:
        Domain name, CaseUpload object
    Returns:
        List of error messages
    """


@extension_point(result_format=ResultFormat.FIRST)
def custom_case_import_operations(domain, row_num, raw_row, fields_to_update, import_context):
    """
    Perform additional operations on a row.
    Directly modify fields_to_update and return it in its final state.
    Return errors inherited from CaseRowError, to skip the row.
    These errors are then shown to the user.

    Parameters:
        Domain name, row number, raw excel row, fields_to_updated
    Returns:
        Tuple: dict of fields to update, list of errors
    """
    return fields_to_update, []
