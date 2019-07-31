from __future__ import absolute_import
from __future__ import unicode_literals

import attr
from django.conf import settings

from corehq.sql_db.routers import forced_citus

from custom.icds_reports.utils.aggregation_helpers.distributed import (
    AggAwcDistributedHelper,
    AggAwcDailyAggregationDistributedHelper,
    AggChildHealthAggregationDistributedHelper,
    AggCcsRecordAggregationDistributedHelper,
    AwcMbtDistributedHelper,
    AwwIncentiveAggregationDistributedHelper,
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
    THRFormV2AggDistributedHelper
)
from custom.icds_reports.utils.aggregation_helpers.monolith import (
    AggAwcHelper,
    AggAwcDailyAggregationHelper,
    AggCcsRecordAggregationHelper,
    AggChildHealthAggregationHelper,
    AggLsHelper,
    AwcInfrastructureAggregationHelper,
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
    THRFormV2AggHelper
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


def all_helpers():
    helpers = {}
    for pair in HELPERS:
        assert pair.validate(), pair
        helpers[pair.monolith.helper_key] = pair
    return helpers


HELPERS_BY_KEY = all_helpers()


def get_helper(key):
    pair = HELPERS_BY_KEY[key]
    if (getattr(settings, 'ICDS_USE_CITUS', False) or forced_citus()) and pair.distributed:
        return pair.distributed
    return pair.monolith
