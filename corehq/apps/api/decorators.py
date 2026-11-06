import base64
from functools import wraps

from django.http import HttpResponse

from corehq.apps.api.cors import ACCESS_CONTROL_ALLOW, add_cors_headers_to_response
from corehq.apps.api.models import ApiUser
from corehq.apps.api.resources.auth import get_rate_limit_identifier
from corehq.apps.api.resources.meta import get_hq_throttle


def api_user_basic_auth(permission, realm=''):
    def real_decorator(view):
        def wrapper(request, *args, **kwargs):
            if 'HTTP_AUTHORIZATION' in request.META:
                auth = request.META['HTTP_AUTHORIZATION'].split()
                if len(auth) == 2:
                    if auth[0].lower() == 'basic':
                        username, password = base64.b64decode(auth[1]).split(':', 1)
                        if ApiUser.auth(username, password, permission):
                            return view(request, *args, **kwargs)

            response = HttpResponse(status=401)
            response['WWW-Authenticate'] = 'Basic realm="%s"' % realm
            return response
        return wrapper
    return real_decorator


def allow_cors(allowed_methods):
    allowed_methods = allowed_methods or []
    # always allow options
    allowed_methods = allowed_methods + ['OPTIONS']

    def decorator(view_func):
        @wraps(view_func)
        def wrapped_view(request, *args, **kwargs):
            if request.method == "OPTIONS":
                response = HttpResponse()
                allowed_methods_header_value = ', '.join(allowed_methods)
                response[ACCESS_CONTROL_ALLOW] = allowed_methods_header_value
                return add_cors_headers_to_response(response, allowed_methods_header_value)
            response = view_func(request, *args, **kwargs)
            if request.method in allowed_methods:
                add_cors_headers_to_response(response)
            return response
        return wrapped_view
    return decorator


def api_throttle(view):
    @wraps(view)
    def wrapped_view(request, *args, **kwargs):
        identifier = get_rate_limit_identifier(request)
        throttle = get_hq_throttle()

        wait_time = throttle.get_throttle_wait_time(identifier)
        if wait_time > 0:
            return HttpResponse(status=429, headers={'Retry-After': wait_time})

        throttle.accessed(identifier, url=request.get_full_path(), request_method=request.method.lower())
        return view(request, *args, **kwargs)
    return wrapped_view
