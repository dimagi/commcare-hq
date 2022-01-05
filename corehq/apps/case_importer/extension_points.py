from typing import List

from corehq.extensions import extension_point, ResultFormat


@extension_point(result_format=ResultFormat.FLATTEN)
def custom_case_upload_file_checks(domain, case_upload) -> List[str]:
    """Perform additional checks on a case upload file.

    Parameters:
        Domain name, CaseUpload object

    Returns:
        List of error messages
    """


@extension_point(result_format=ResultFormat.FIRST)
def custom_case_upload_operations(domain, row_num, raw_row, fields_to_update):
    """
    Perform additional operations on row and return updates to be done.
    Raise an error with custom class inherited from CaseRowError to skip the row

    Parameters:
        Domain name, row number, raw excel row, fields_to_updated

    Returns:
        Final fields to update, error
    """
