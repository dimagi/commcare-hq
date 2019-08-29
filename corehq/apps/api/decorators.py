import base64

from django.http import HttpResponse

from corehq.apps.api.models import ApiUser


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
