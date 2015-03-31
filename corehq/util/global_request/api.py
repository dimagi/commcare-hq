import threading

_thread_local = threading.local()


def get_request():
    try:
        return _thread_local.request
    except AttributeError:
        return None


def set_request(request):
    _thread_local.request = request
