from __future__ import absolute_import
from __future__ import unicode_literals

from datetime import date
import os

from corehq.util.test_utils import generate_cases

from custom.icds_reports.tests import OUTPUT_PATH
from custom.icds_reports.utils.aggregation_helpers.awc_infrastructure import AwcInfrastructureAggregationHelper
from custom.icds_reports.utils.aggregation_helpers.aww_incentive import AwwIncentiveAggregationHelper
from custom.icds_reports.utils.aggregation_helpers.complementary_forms import ComplementaryFormsAggregationHelper
from custom.icds_reports.utils.aggregation_helpers.daily_attendance import DailyAttendanceAggregationHelper
from custom.icds_reports.utils.aggregation_helpers.delivery_forms import DeliveryFormsAggregationHelper
from custom.icds_reports.utils.aggregation_helpers.growth_monitoring_forms import GrowthMonitoringFormsAggregationHelper
from custom.icds_reports.utils.aggregation_helpers.thr_forms_child_health import THRFormsChildHealthAggregationHelper
from custom.icds_reports.utils.aggregation_helpers.thr_froms_ccs_record import THRFormsCcsRecordAggregationHelper
from custom.icds_reports.utils.aggregation_helpers.postnatal_care_forms_ccs_record import PostnatalCareFormsCcsRecordAggregationHelper
from custom.icds_reports.utils.aggregation_helpers.postnatal_care_forms_child_health import PostnatalCareFormsChildHealthAggregationHelper
from custom.icds_reports.utils.aggregation_helpers.birth_preparedness_forms import BirthPreparednessFormsAggregationHelper
from custom.icds_reports.tests.test_aggregation_script import AggregationScriptTestBase
from custom.icds_reports.tasks import build_incentive_report

DASHBOARD_TABLE_PATH = os.path.join(OUTPUT_PATH, 'dashboard_table_dumps')


@generate_cases([
    (AwcInfrastructureAggregationHelper, [date(2017, 4, 1), date(2017, 5, 1)], 'awc_id'),
    (ComplementaryFormsAggregationHelper, [date(2017, 4, 1), date(2017, 5, 1)], 'case_id'),
    (DeliveryFormsAggregationHelper, [date(2017, 4, 1), date(2017, 5, 1)], 'case_id'),
    (PostnatalCareFormsCcsRecordAggregationHelper, [date(2017, 4, 1), date(2017, 5, 1)], 'case_id'),
    (THRFormsChildHealthAggregationHelper, [date(2017, 4, 1), date(2017, 5, 1)], 'case_id'),
    (THRFormsCcsRecordAggregationHelper, [date(2017, 4, 1), date(2017, 5, 1)], 'case_id'),
    (BirthPreparednessFormsAggregationHelper, [date(2017, 4, 1), date(2017, 5, 1)], 'case_id'),
    (GrowthMonitoringFormsAggregationHelper, [date(2017, 2, 1), date(2017, 3, 1)], 'case_id'),
    (PostnatalCareFormsChildHealthAggregationHelper, [date(2017, 4, 1), date(2017, 5, 1)], 'case_id'),
], AggregationScriptTestBase)
def test_dashboard_table_data(self, helper, months, sort_key):
    tablenames = []
    for month in months:
        for state_name in ["st1", "st2"]:
            helper_obj = helper(state_name, month)
            try:
                tablename = helper_obj.tablename
            except AttributeError:
                tablename = helper_obj.generate_child_tablename(month)
            tablenames.append(tablename)

    for table in set(tablenames):
        self._load_and_compare_data(
            tablename,
            os.path.join(DASHBOARD_TABLE_PATH, '{}_sorted.csv'.format(tablename)),
            sort_key=[sort_key]
        )


class AwwIncentiveAndDailyAttendanceTest(AggregationScriptTestBase):
    def test_aww_incetive(self):
        for month in [date(2017, 4, 1), date(2017, 5, 1)]:
            # this is not built in setUpModule()
            build_incentive_report(month)
            import pdb; pdb.set_trace()
            for state in ["st1", "st2"]:
                tablename = AwwIncentiveAggregationHelper(state, month).generate_child_tablename(month)
                self._load_and_compare_data(
                    tablename,
                    os.path.join(DASHBOARD_TABLE_PATH, '{}_sorted.csv'.format(tablename)),
                    sort_key=['case_id']
                )

    def test_daily_attandance(self):
        for month in [date(2017, 4, 1), date(2017, 5, 1)]:
            tablename = DailyAttendanceAggregationHelper(month).tablename
            self._load_and_compare_data(
                tablename,
                os.path.join(DASHBOARD_TABLE_PATH, '{}_sorted.csv'.format(tablename)),
                sort_key=['month']
            )
