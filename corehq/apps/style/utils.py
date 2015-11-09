import threading

_thread_local = threading.local()

BOOTSTRAP_2 = 'bootstrap-2'
BOOTSTRAP_3 = 'bootstrap-3'


def get_bootstrap_version():
    try:
        bootstrap_version = _thread_local.BOOTSTRAP_VERSION
    except AttributeError:
        bootstrap_version = BOOTSTRAP_2
    return bootstrap_version


def set_bootstrap_version3():
    _thread_local.BOOTSTRAP_VERSION = BOOTSTRAP_3


def set_bootstrap_version2():
    _thread_local.BOOTSTRAP_VERSION = BOOTSTRAP_2


def format_angular_error(error_msg, additional_data=None,
                         log_error=False, exception=None, request=None):
    """Gets the standard angular async error response.
    :param error_msg: A string that is the error message you'd like to return
    :param additional_data: a dictionary of additional data you'd like to pass
    :return: {
        'error': <error_msg>,
        <...additional_data...>,
    }
    """
    resp = {
        'error': error_msg,
    }
    if isinstance(additional_data, dict):
        resp.update(additional_data)
    return resp


def format_angular_success(additional_data=None):
    """Gets the standard angular async SUCCESS response.
    :param additional_data: a dictionary of additional data you'd like to pass
    :return: {
        'success': True,
        <...additional_data...>,
    }
    """
    resp = {
        'success': True,
    }
    if isinstance(additional_data, dict):
        resp.update(additional_data)
    return resp
