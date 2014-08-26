import inspect


def set_file_download(response, filename):
    response["Content-Disposition"] = 'attachment; filename="%s"' % filename


def get_request():
    """
    Walk up the stack, return the nearest first argument named "request".

    taken from http://nedbatchelder.com/blog/201008/global_django_requests.html
    """
    frame = None
    try:
        for f in inspect.stack()[1:]:
            frame = f[0]
            code = frame.f_code
            if code.co_varnames and code.co_varnames[0] in ("request", "req"):
                return frame.f_locals[code.co_varnames[0]]
    finally:
        del frame
