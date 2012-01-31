from cStringIO import StringIO
from functools import wraps

def get_file(filename):
    """
    This decorator is meant mainly for views that accept a file post.
    It will put the file into the request object as request.file
    for easy access.

    Usage:

    @get_file('xform')
    def view(request, ...):
        ...

    or simply

    @get_file
    def view(request, ...):
        ...

    which defaults to using the filename 'file'

    """
    def decorator(view, filename=filename):
        @wraps(view)
        def view_prime(request, *args, **kwargs):
            if request.method == 'POST':
                if request.META['CONTENT_TYPE'].startswith('multipart/form-data'):
                    request.file = request.FILES[filename]
                    for key, item in request.FILES.items():
                        if key != filename:
                            request.other_files[key] = item
                else:
                    # I have had some trouble with request.raw_post_data not preserving newlines...
                    request.file = StringIO(request.raw_post_data)
                    request.other_files = {}
            return view(request, *args, **kwargs)
        return view_prime
    if hasattr(filename, '__call__'):
        return decorator(filename, filename='file')
    else:
        return decorator
