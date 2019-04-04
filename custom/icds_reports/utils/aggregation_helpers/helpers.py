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
    HelperPair(AggAwcHelper, AggAwcDistributedHelper),
    HelperPair(AggAwcDailyAggregationHelper, AggAwcDailyAggregationDistributedHelper),
    HelperPair(AggCcsRecordAggregationHelper, AggCcsRecordAggregationDistributedHelper),
    HelperPair(AggChildHealthAggregationHelper, AggChildHealthAggregationDistributedHelper),
    HelperPair(AggLsHelper, None),
    HelperPair(AwcInfrastructureAggregationHelper, None),
    HelperPair(AwwIncentiveAggregationHelper, AwwIncentiveAggregationDistributedHelper),
    HelperPair(AwcMbtHelper, AwcMbtDistributedHelper),
    HelperPair(BirthPreparednessFormsAggregationHelper, BirthPreparednessFormsAggregationDistributedHelper),
    HelperPair(ChildHealthMbtHelper, ChildHealthMbtDistributedHelper),
    HelperPair(ChildHealthMonthlyAggregationHelper, ChildHealthMonthlyAggregationDistributedHelper),
    HelperPair(CcsMbtHelper, CcsMbtDistributedHelper),
    HelperPair(CcsRecordMonthlyAggregationHelper, CcsRecordMonthlyAggregationDistributedHelper),
    HelperPair(ComplementaryFormsAggregationHelper, ComplementaryFormsAggregationDistributedHelper),
    HelperPair(ComplementaryFormsCcsRecordAggregationHelper, ComplementaryFormsCcsRecordAggregationDistributedHelper),
    HelperPair(DailyAttendanceAggregationHelper, DailyAttendanceAggregationDistributedHelper),
    HelperPair(DailyFeedingFormsChildHealthAggregationHelper, DailyFeedingFormsChildHealthAggregationDistributedHelper),
    HelperPair(DeliveryFormsAggregationHelper, DeliveryFormsAggregationDistributedHelper),
    HelperPair(GrowthMonitoringFormsAggregationHelper, GrowthMonitoringFormsAggregationDistributedHelper),
    HelperPair(InactiveAwwsAggregationHelper, InactiveAwwsAggregationDistributedHelper),
    HelperPair(LocationAggregationHelper, LocationAggregationDistributedHelper),
    HelperPair(LSAwcMgtFormAggHelper, LSAwcMgtFormAggDistributedHelper),
    HelperPair(LSBeneficiaryFormAggHelper, LSBeneficiaryFormAggDistributedHelper),
    HelperPair(LSVhndFormAggHelper, LSVhndFormAggDistributedHelper),
    HelperPair(PostnatalCareFormsCcsRecordAggregationHelper, PostnatalCareFormsCcsRecordAggregationDistributedHelper),
    HelperPair(PostnatalCareFormsChildHealthAggregationHelper, PostnatalCareFormsChildHealthAggregationDistributedHelper),
    HelperPair(THRFormsChildHealthAggregationHelper, THRFormsChildHealthAggregationDistributedHelper),
    HelperPair(THRFormsCcsRecordAggregationHelper, THRFormsCcsRecordAggregationDistributedHelper),
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
