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


def is_logged_in(request):
    """
    Determine if the requesting user is fully logged in, taking 2FA into
    consideration.

    A user with 2FA enabled must also be verified.
    """
    user = request.user
    if not user.is_authenticated:
        return False
    if not default_device(user):
        return True
    return user.is_verified()
