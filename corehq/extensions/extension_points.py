from typing import List

from corehq.extensions import extension_point, ResultFormat


@extension_point(result_format=ResultFormat.FLATTEN)
def domain_specific_urls() -> List[str]:
    """Add domain specific URLs to the Django URLs module.

    Parameters:
        None

    Returns:
        A list of URL module strings
    """
