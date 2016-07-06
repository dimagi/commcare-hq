import logging
import threading


def format_angular_error(error_msg, additional_data=None,
                         log_error=False, exception=None):
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
    if log_error:
        if exception:
            logging.exception(exception)
        else:
            logging.error(error_msg)

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
