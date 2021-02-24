from memoized import memoized
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


@extension_point(result_format=ResultFormat.FIRST)
def custom_clean_password(password) -> Optional[str]:
    """Custom function to ensure that password meets requirements

    Returns:
        An error message to show
    """


@memoized
def has_custom_clean_password():
    # the environment has a custom clean password method set
    return bool(custom_clean_password.extensions)
