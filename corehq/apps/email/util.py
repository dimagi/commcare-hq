from memoized import memoized

import settings
from dimagi.utils.modules import to_function


class BadEmailConfigException(Exception):
    pass


def _get_backend_classes(backend_list):
    """
    Returns a dictionary of {api id: class} for all installed Email backends.
    """
    result = {}

    for backend_class in backend_list:
        cls = to_function(backend_class)
        api_id = cls.get_api_id()
        if api_id in result:
            raise BadEmailConfigException(f"Cannot have more than one backend with the same \
                                            api id. Duplicate found for: {api_id}")
        result[api_id] = cls
    return result


@memoized
def get_email_backend_classes():
    return _get_backend_classes(settings.EMAIL_SQL_BACKENDS)
