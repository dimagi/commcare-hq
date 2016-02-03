from .const import TRANSFORM_FUNCTIONS
from .exceptions import ExportInvalidTransform


def is_valid_transform(value):
    if value is None:
        return True
    if value in TRANSFORM_FUNCTIONS:
        return True

    raise ExportInvalidTransform('{} is not a valid transform'.format(value))
