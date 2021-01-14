from typing import Optional

from django.utils.translation import ugettext as _
from memoized import memoized
from pyzxcvbn import zxcvbn

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
def validate_password_rules(password) -> Optional[str]:
    """Ensure that password meets requirements

    Returns:
        An error message to show
    """
    strength = zxcvbn(password, user_inputs=['commcare', 'hq', 'dimagi', 'commcarehq'])
    if strength['score'] < 2:
        return _('Password is not strong enough. Try making your password more complex.')


@memoized
def has_custom_clean_password():
    # the environment has a custom clean password method set
    return bool(validate_password_rules.extensions)
