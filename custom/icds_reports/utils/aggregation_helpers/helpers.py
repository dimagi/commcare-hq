import attr
from django.conf import settings

from custom.icds_reports.utils.aggregation_helpers.distributed import *
from custom.icds_reports.utils.aggregation_helpers.monolith import *


@attr.s
class HelperPair(object):
    monolith = attr.ib(default=None)
    distributed = attr.ib(default=None)

    def validate(self):
        return not self.distributed or self.monolith.helper_key == self.distributed.helper_key


HELPERS = [
    HelperPair(AggCcsRecordAggregationHelper, AggCcsRecordAggregationDistributedHelper),
    HelperPair(AggChildHealthAggregationHelper, AggChildHealthAggregationDistributedHelper),
    HelperPair(AwcInfrastructureAggregationHelper, None),
    HelperPair(AwwIncentiveAggregationHelper, None),
    HelperPair(LSAwcMgtFormAggHelper, LSAwcMgtFormAggDistributedHelper),
    HelperPair(LSBeneficiaryFormAggHelper, LSBeneficiaryFormAggDistributedHelper),
    HelperPair(LSVhndFormAggHelper, LSVhndFormAggDistributedHelper),
    HelperPair(AggLsHelper, None),
    HelperPair(BirthPreparednessFormsAggregationHelper, BirthPreparednessFormsAggregationDistributedHelper),
    HelperPair(CcsRecordMonthlyAggregationHelper, CcsRecordMonthlyAggregationDistributedHelper),
    HelperPair(ChildHealthMonthlyAggregationHelper, ChildHealthMonthlyAggregationDistributedHelper),
    HelperPair(ComplementaryFormsAggregationHelper, ComplementaryFormsAggregationDistributedHelper),
    HelperPair(ComplementaryFormsCcsRecordAggregationHelper, ComplementaryFormsCcsRecordAggregationDistributedHelper),
    HelperPair(DailyFeedingFormsChildHealthAggregationHelper, DailyFeedingFormsChildHealthAggregationDistributedHelper),
    HelperPair(DeliveryFormsAggregationHelper, DeliveryFormsAggregationDistributedHelper),
    HelperPair(GrowthMonitoringFormsAggregationHelper, GrowthMonitoringFormsAggregationDistributedHelper),
    HelperPair(InactiveAwwsAggregationHelper, InactiveAwwsAggregationDistributedHelper),
    HelperPair(PostnatalCareFormsCcsRecordAggregationHelper, PostnatalCareFormsCcsRecordAggregationDistributedHelper),
    HelperPair(PostnatalCareFormsChildHealthAggregationHelper, PostnatalCareFormsChildHealthAggregationDistributedHelper),
    HelperPair(THRFormsChildHealthAggregationHelper, THRFormsChildHealthAggregationDistributedHelper),
    HelperPair(THRFormsCcsRecordAggregationHelper, THRFormsCcsRecordAggregationDistributedHelper),
    HelperPair(AggAwcHelper, AggAwcDistributedHelper),
    HelperPair(AggAwcDailyAggregationHelper, AggAwcDailyAggregationDistributedHelper),
    HelperPair(LocationAggregationHelper, None),
    HelperPair(DailyAttendanceAggregationHelper, DailyAttendanceAggregationDistributedHelper),
    HelperPair(CcsMbtHelper, CcsMbtDistributedHelper),
    HelperPair(ChildHealthMbtHelper, ChildHealthMbtDistributedHelper),
    HelperPair(AwcMbtHelper, AwcMbtDistributedHelper),
]


def all_helpers():
    helpers = {}
    for pair in HELPERS:
        assert pair.validate(), pair
        helpers[pair.monolith.helper_key] = pair
    return helpers


HELPERS_BY_KEY = all_helpers()


def get_helper(key):
    pair = HELPERS_BY_KEY[key]
    if getattr(settings, 'ICDS_USE_CITS', False) and pair.distributed:
        return pair.distributed
    return pair.monolith
