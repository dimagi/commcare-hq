from .const import TRANSFORM_FUNCTIONS
from .exceptions import ExportInvalidTransform


def is_valid_transform(value):
    for transform in value:
        if transform not in TRANSFORM_FUNCTIONS:
            raise ExportInvalidTransform('{} is not a valid transform'.format(value))
