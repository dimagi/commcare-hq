from django.conf import settings


def get_request_data(request):
    """
    OneLogin's python3-saml library expects a very specifically formatted
    "request_data" object as it is framework agnostic and each framework
    (eg flask, django, tornado) has its own way of populating the built in
    request object
    :param request:
    :return: dictionary with fields that python3-saml expects
    """
    return {
        'https': 'on' if request.is_secure() else 'off',
        'http_host': request.META['HTTP_HOST'],
        'script_name': request.META['PATH_INFO'],

        # see https://github.com/onelogin/python3-saml/issues/83
        'server_port': (request.META['SERVER_PORT']
                        if settings.SAML2_DEBUG else '443'),

        'get_data': request.GET.copy(),
        'post_data': request.POST.copy(),
    }
