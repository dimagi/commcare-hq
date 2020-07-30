from typing import Optional

from corehq.extensions import extension_point, ResultFormat


@extension_point(result_format=ResultFormat.FIRST)
def custom_domain_module(domain) -> Optional[str]:
    """Custom reporting modules

    Parameters:
        domain: the name of the domain

    Returns:
        A string of the python path to the module for the domain, or None
    """
