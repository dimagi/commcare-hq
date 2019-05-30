from __future__ import print_function
from __future__ import unicode_literals
from __future__ import absolute_import

from .exceptions import LimitTypeDoesNotExist
from .limits import LIMIT_TYPES
from .models import ProjectUsageLimit


LIMIT_TYPES_BY_NAME = {limit_type.name: limit_type for limit_type in LIMIT_TYPES}


def get_limit_type(limit_name):
    try:
        return LIMIT_TYPES_BY_NAME[limit_name]
    except KeyError:
        raise LimitTypeDoesNotExist(limit_name)


def get_usage_limit(domain, limit_name):
    limit_type = get_limit_type(limit_name)
    try:
        ProjectUsageLimit.objects.get(domain=domain, limit_name=limit_type.name).value
    except ProjectUsageLimit.DoesNotExist:
        return limit_type.default


def set_usage_limit(domain, limit_name, limit_value):
    # raises the right error if limit_type doesn't exist
    # proactively instead of waiting for the DB to do it
    limit_type = get_limit_type(limit_name)
    ProjectUsageLimit.objects.update_or_create(
        {'value': limit_value},
        domain=domain,
        limit_name=limit_type.name
    )
