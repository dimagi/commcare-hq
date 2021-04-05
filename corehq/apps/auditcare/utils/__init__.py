from django.conf import settings

DEFAULT_TEMPLATE = "auditcare/auditcare_config_broken.html"


def login_template():
    return getattr(settings, 'LOGIN_TEMPLATE', DEFAULT_TEMPLATE)


def logout_template():
    return getattr(settings, 'LOGGEDOUT_TEMPLATE', DEFAULT_TEMPLATE)


def to_django_header(value):
    """Convert header name to a key to be used with `request.META`"""
    return 'HTTP_' + value.upper().replace('-', '_')
