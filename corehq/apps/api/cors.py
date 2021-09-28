

ACCESS_CONTROL_ALLOW = 'Allow'
ACCESS_CONTROL_ALLOW_HEADERS = 'Access-Control-Allow-Headers'
ACCESS_CONTROL_ALLOW_ORIGIN = 'Access-Control-Allow-Origin'


def add_cors_headers_to_response(response):
    response[ACCESS_CONTROL_ALLOW_ORIGIN] = '*'
    response[ACCESS_CONTROL_ALLOW_HEADERS] = 'Content-Type, Authorization'
    return response
