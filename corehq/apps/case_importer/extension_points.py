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
def custom_case_import_operations(domain, row_num, raw_row, fields_to_update):
    """
    Perform additional operations on a row and return final updates to be done.
    To skip the row return error messages. These messages are then shown to the user.

    Parameters:
        Domain name, row number, raw excel row, fields_to_updated
    Returns:
        Final fields to update, error messages
    """
    return fields_to_update, []
