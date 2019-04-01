from __future__ import absolute_import
from __future__ import unicode_literals

from datetime import date

from six.moves import range

from corehq.apps.locations.models import SQLLocation

from .agg_ccs_record import AggCcsRecordAggregationHelper
from .agg_child_health import AggChildHealthAggregationHelper
from .awc_infrastructure import AwcInfrastructureAggregationHelper
from .aww_incentive import AwwIncentiveAggregationHelper
from .ls_awc_visit_form import LSAwcMgtFormAggHelper
from .ls_beneficiary_form import LSBeneficiaryFormAggHelper
from .ls_vhnd_form import LSVhndFormAggHelper
from .agg_ls_data import AggLsHelper
from .birth_preparedness_forms import BirthPreparednessFormsAggregationHelper
from .ccs_record_monthly import CcsRecordMonthlyAggregationHelper
from .child_health_monthly import ChildHealthMonthlyAggregationHelper
from .complementary_forms import ComplementaryFormsAggregationHelper
from .complementary_forms_ccs_record import ComplementaryFormsCcsRecordAggregationHelper
from .daily_feeding_forms_child_health import DailyFeedingFormsChildHealthAggregationHelper
from .delivery_forms import DeliveryFormsAggregationHelper
from .growth_monitoring_forms import GrowthMonitoringFormsAggregationHelper
from .inactive_awws import InactiveAwwsAggregationHelper
from .postnatal_care_forms_ccs_record import PostnatalCareFormsCcsRecordAggregationHelper
from .postnatal_care_forms_child_health import PostnatalCareFormsChildHealthAggregationHelper
from .thr_forms_child_health import THRFormsChildHealthAggregationHelper
from .thr_froms_ccs_record import THRFormsCcsRecordAggregationHelper
from .agg_awc import AggAwcHelper
from .agg_awc_daily import AggAwcDailyAggregationHelper
from .awc_location import LocationAggregationHelper
from .daily_attendance import DailyAttendanceAggregationHelper
# excluded due to circular dependency
# from .mbt import CcsMbtHelper, ChildHealthMbtHelper, AwcMbtHelper


def recalculate_aggregate_table(model_class):
    """Expects a class (not instance) of models.Model

    Not expected to last past 2018 (ideally past May) so this shouldn't break in 2019
    """
    state_ids = (
        SQLLocation.objects
        .filter(domain='icds-cas', location_type__name='state')
        .values_list('location_id', flat=True)
    )

    for state_id in state_ids:
        for year in (2015, 2016, 2017):
            for month in range(1, 13):
                model_class.aggregate(state_id, date(year, month, 1))

        for month in range(1, date.today().month + 1):
            model_class.aggregate(state_id, date(2018, month, 1))
