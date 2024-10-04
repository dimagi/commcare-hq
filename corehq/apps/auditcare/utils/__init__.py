
def to_django_header(value):
    """Convert header name to a key to be used with `request.META`"""
    return 'HTTP_' + value.upper().replace('-', '_')
