import types

from functools import partial
from operator import isCallable

from django.http import HttpRequest, HttpResponse

from decorator import decorator

from django_digest import HttpDigestAuthenticator

def _httpdigest(authenticator, f, *args, **kwargs):
    # 'f' might be a function, in which case args[0] is 'request'
    if len(args) >= 1 and isinstance(args[0], HttpRequest):
        request = args[0]
    # 'f' could also be a method, in which case args[0] is 'self' and
    # args[1] is 'request'
    elif len(args) >= 2 and isinstance(args[1], HttpRequest):
        request = args[1]
    else:
        raise Exception("Neither args[0] nor args[1] is an HttpRequest.")

    if not authenticator.authenticate(request):
        return authenticator.build_challenge_response()

    response = f(*args, **kwargs)
    if hasattr(response, 'status_code') and response.status_code in [401, 403]:
        return authenticator.build_challenge_response()

    return response
    

def httpdigest(*args, **kwargs):
    '''
    May be used in one of three ways:
    * as a decorator factory (with the arguments being parameters to an instance of
    HttpDigestAuthenticator used to protect the decorated view)
    * as a decorator (protecting the decorated view with a default-constructed instance of
    HttpDigestAuthenticator)
    * as a decorator factory (with the argument being a pre-constructed HttpDigestAuthenticator
    instance used to protect the decorated view)
    '''
    if len(args) == 1 and not kwargs and isCallable(args[0]):
        authenticator = HttpDigestAuthenticator()
        return decorator(partial(_httpdigest, authenticator), args[0])

    if len(args) == 1 and not kwargs and isinstance(args[0], HttpDigestAuthenticator):
        authenticator = args[0]
    else:
        authenticator = HttpDigestAuthenticator(*args, **kwargs)

    return lambda(f): decorator(partial(_httpdigest, authenticator), f)
