from django.conf import settings


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
