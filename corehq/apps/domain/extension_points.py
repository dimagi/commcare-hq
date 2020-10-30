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
def custom_password_clean(txt_password) -> None:
    """Custom function to ensures that password meets requirements"""


@extension_point(result_format=ResultFormat.FIRST)
def additional_authentication_form_fields() -> Optional[dict]:
    """Custom form fields to add to all login forms"""


@extension_point(result_format=ResultFormat.FIRST)
def additional_password_reset_form_fields() -> Optional[dict]:
    """Custom form fields to add to all login forms"""


@extension_point(result_format=ResultFormat.FIRST)
def additional_invitation_form_fields() -> Optional[dict]:
    """Custom form fields to add to all login forms"""
