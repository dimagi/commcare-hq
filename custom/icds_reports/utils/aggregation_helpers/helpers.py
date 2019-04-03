from collections import defaultdict

import attr
from django.conf import settings
from memoized import memoized

from corehq.sql_db.util import _get_all_nested_subclasses
from custom.icds_reports.utils.aggregation_helpers.distributed.base import DistributedAggregationHelper
from custom.icds_reports.utils.aggregation_helpers.monolith.base import AggregationHelper


@attr.s
class HelperPair(object):
    monolith = attr.ib(default=None)
    distributed = attr.ib(default=None)


@memoized
def all_helpers():
    # this is a bit dodge but these are required otherwise they don't get found by the subclass helper
    # import must be inside function to avoid circular dependency
    from .monolith.mbt import CcsMbtHelper, ChildHealthMbtHelper, AwcMbtHelper
    from .distributed.mbt import CcsMbtDistributedHelper, ChildHealthMbtDistributedHelper, AwcMbtDistributedHelper

    helpers = defaultdict(lambda: HelperPair())

    # not enthralled by this solution but it beat the copy paste I was doing before
    for helper in _get_all_nested_subclasses(AggregationHelper):
        if helper.helper_key:
            helpers[helper.helper_key].monolith = helper

    for helper in _get_all_nested_subclasses(DistributedAggregationHelper):
        if helper.helper_key:
            helpers[helper.helper_key].distributed = helper

    for pair in helpers.values():
        assert pair.monolith, pair
    return helpers


def get_helper(key):
    pair = all_helpers()[key]
    if getattr(settings, 'ICDS_USE_CITS', False) and pair.distributed:
        return pair.distributed
    return pair.monolith
