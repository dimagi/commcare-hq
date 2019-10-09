import attr

from custom.icds_reports.utils.aggregation_helpers.distributed import (
    AggAwcDailyAggregationDistributedHelper,
    AggAwcDistributedHelper,
    AggCcsRecordAggregationDistributedHelper,
    AggChildHealthAggregationDistributedHelper,
    AggLsHelper,
    AwcMbtDistributedHelper,
    AwwIncentiveAggregationDistributedHelper,
    AwcInfrastructureAggregationHelper,
    BirthPreparednessFormsAggregationDistributedHelper,
    CcsMbtDistributedHelper,
    CcsRecordMonthlyAggregationDistributedHelper,
    ChildHealthMbtDistributedHelper,
    ChildHealthMonthlyAggregationDistributedHelper,
    ComplementaryFormsAggregationDistributedHelper,
    ComplementaryFormsCcsRecordAggregationDistributedHelper,
    DailyAttendanceAggregationDistributedHelper,
    DailyFeedingFormsChildHealthAggregationDistributedHelper,
    DeliveryFormsAggregationDistributedHelper,
    GrowthMonitoringFormsAggregationDistributedHelper,
    InactiveAwwsAggregationDistributedHelper,
    LocationAggregationDistributedHelper,
    LSAwcMgtFormAggDistributedHelper,
    LSBeneficiaryFormAggDistributedHelper,
    LSVhndFormAggDistributedHelper,
    PostnatalCareFormsCcsRecordAggregationDistributedHelper,
    PostnatalCareFormsChildHealthAggregationDistributedHelper,
    THRFormsCcsRecordAggregationDistributedHelper,
    THRFormsChildHealthAggregationDistributedHelper,
    THRFormV2AggDistributedHelper,
)
from custom.icds_reports.utils.aggregation_helpers.monolith import (
    AggAwcDailyAggregationHelper,
    AggAwcHelper,
    AggCcsRecordAggregationHelper,
    AggChildHealthAggregationHelper,
    AwcMbtHelper,
    AwwIncentiveAggregationHelper,
    BirthPreparednessFormsAggregationHelper,
    CcsMbtHelper,
    CcsRecordMonthlyAggregationHelper,
    ChildHealthMbtHelper,
    ChildHealthMonthlyAggregationHelper,
    ComplementaryFormsAggregationHelper,
    ComplementaryFormsCcsRecordAggregationHelper,
    DailyAttendanceAggregationHelper,
    DailyFeedingFormsChildHealthAggregationHelper,
    DeliveryFormsAggregationHelper,
    GrowthMonitoringFormsAggregationHelper,
    InactiveAwwsAggregationHelper,
    LocationAggregationHelper,
    LSAwcMgtFormAggHelper,
    LSBeneficiaryFormAggHelper,
    LSVhndFormAggHelper,
    PostnatalCareFormsCcsRecordAggregationHelper,
    PostnatalCareFormsChildHealthAggregationHelper,
    THRFormsCcsRecordAggregationHelper,
    THRFormsChildHealthAggregationHelper,
    THRFormV2AggHelper,
)


@attr.s
class HelperPair(object):
    monolith = attr.ib(default=None)
    distributed = attr.ib(default=None)

    def validate(self):
        return not self.distributed or self.monolith.helper_key == self.distributed.helper_key


HELPERS = [
    HelperPair(
        AggAwcHelper, AggAwcDistributedHelper
    ),
    HelperPair(
        AggAwcDailyAggregationHelper, AggAwcDailyAggregationDistributedHelper
    ),
    HelperPair(
        AggCcsRecordAggregationHelper, AggCcsRecordAggregationDistributedHelper
    ),
    HelperPair(
        AggChildHealthAggregationHelper, AggChildHealthAggregationDistributedHelper
    ),
    HelperPair(
        AggLsHelper, None
    ),
    HelperPair(
        AwcInfrastructureAggregationHelper, None
    ),
    HelperPair(
        AwwIncentiveAggregationHelper, AwwIncentiveAggregationDistributedHelper
    ),
    HelperPair(
        AwcMbtHelper, AwcMbtDistributedHelper
    ),
    HelperPair(
        BirthPreparednessFormsAggregationHelper, BirthPreparednessFormsAggregationDistributedHelper
    ),
    HelperPair(
        ChildHealthMbtHelper, ChildHealthMbtDistributedHelper
    ),
    HelperPair(
        ChildHealthMonthlyAggregationHelper, ChildHealthMonthlyAggregationDistributedHelper
    ),
    HelperPair(
        CcsMbtHelper, CcsMbtDistributedHelper
    ),
    HelperPair(
        CcsRecordMonthlyAggregationHelper, CcsRecordMonthlyAggregationDistributedHelper
    ),
    HelperPair(
        ComplementaryFormsAggregationHelper, ComplementaryFormsAggregationDistributedHelper
    ),
    HelperPair(
        ComplementaryFormsCcsRecordAggregationHelper, ComplementaryFormsCcsRecordAggregationDistributedHelper
    ),
    HelperPair(
        DailyAttendanceAggregationHelper, DailyAttendanceAggregationDistributedHelper
    ),
    HelperPair(
        DailyFeedingFormsChildHealthAggregationHelper, DailyFeedingFormsChildHealthAggregationDistributedHelper
    ),
    HelperPair(
        DeliveryFormsAggregationHelper, DeliveryFormsAggregationDistributedHelper
    ),
    HelperPair(
        GrowthMonitoringFormsAggregationHelper, GrowthMonitoringFormsAggregationDistributedHelper
    ),
    HelperPair(
        InactiveAwwsAggregationHelper, InactiveAwwsAggregationDistributedHelper
    ),
    HelperPair(
        LocationAggregationHelper, LocationAggregationDistributedHelper
    ),
    HelperPair(
        LSAwcMgtFormAggHelper, LSAwcMgtFormAggDistributedHelper
    ),
    HelperPair(
        LSBeneficiaryFormAggHelper, LSBeneficiaryFormAggDistributedHelper
    ),
    HelperPair(
        LSVhndFormAggHelper, LSVhndFormAggDistributedHelper
    ),
    HelperPair(
        PostnatalCareFormsCcsRecordAggregationHelper, PostnatalCareFormsCcsRecordAggregationDistributedHelper
    ),
    HelperPair(
        PostnatalCareFormsChildHealthAggregationHelper, PostnatalCareFormsChildHealthAggregationDistributedHelper
    ),
    HelperPair(
        THRFormsChildHealthAggregationHelper, THRFormsChildHealthAggregationDistributedHelper
    ),
    HelperPair(
        THRFormsCcsRecordAggregationHelper, THRFormsCcsRecordAggregationDistributedHelper
    ),
    HelperPair(
        THRFormV2AggHelper, THRFormV2AggDistributedHelper
    )
]
