

ACCESS_CONTROL_ALLOW = 'Allow'
ACCESS_CONTROL_ALLOW_HEADERS = 'Access-Control-Allow-Headers'
ACCESS_CONTROL_ALLOW_ORIGIN = 'Access-Control-Allow-Origin'
ACCESS_CONTROL_ALLOW_METHODS = 'Access-Control-Allow-Methods'


def add_cors_headers_to_response(response, allow_methods: str = ''):
    response[ACCESS_CONTROL_ALLOW_ORIGIN] = '*'
    response[ACCESS_CONTROL_ALLOW_HEADERS] = 'Content-Type, Authorization'
    if allow_methods:
        response[ACCESS_CONTROL_ALLOW_METHODS] = allow_methods
    return response
