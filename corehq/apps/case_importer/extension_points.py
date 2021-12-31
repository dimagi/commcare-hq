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
