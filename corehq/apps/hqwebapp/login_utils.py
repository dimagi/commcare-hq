from django.conf import settings

from two_factor.utils import default_device


def get_custom_login_page(host):
    """
    Returns the configured custom login template for the request, if matched, else None
    :param request:
    :return:
    """
    custom_landing_page = settings.CUSTOM_LANDING_TEMPLATE
    if custom_landing_page:
        if isinstance(custom_landing_page, str):
            return custom_landing_page
        else:
            template_name = custom_landing_page.get(host)
            if template_name is None:
                return custom_landing_page.get('default')
            else:
                return template_name


def is_logged_in(user):
    """
    Determine if user is fully logged in, taking into consideration 2FA
    If 2FA is enabled, the user needs to be verified in order to return True rather than just authenticated
    :param user: django user (django.contrib.auth.models.User)
    """
    return user.is_verified() if default_device(user) else user.is_authenticated
