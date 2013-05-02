# coding=utf-8
from numbers import Number
from corehq.apps.reports.fields import DatespanField
from corehq.apps.reports.standard import DatespanMixin
from dimagi.utils.decorators.memoized import memoized

from sqlagg import *
from sqlagg.columns import *

from ..sqlreport import SqlTabularReport, Column, AggregateColumn


def username(report, key):
    return report.usernames_demo[key]


def combine_indicator(num, denom):
    if isinstance(num, Number) and isinstance(denom, Number):
        if denom != 0:
            return num * 100 / denom
        else:
            return 0
    else:
        return None


def test_report(report, keys=None, filters=None, group_by=None):
    class TestReportInst(report):
        database = "test_commcarehq"
        @property
        def keys(self):
            return keys

        @property
        def filters(self):
            return filters

        @property
        def group_by(self):
            return group_by

    return TestReportInst


class UserTestReport(SqlTabularReport, DatespanMixin):
    name = "SQL Demo"
    slug = "sql_demo"
    field_classes = (DatespanField,)
    table_name = "user_report_data"

    @property
    def usernames_demo(self):
        return {"user1": "Joe", "user2": "Bob", 'user3': "Gill"}

    @property
    def filter_values(self):
        return {
            "startdate": self.datespan.startdate_param_utc,
            "enddate": self.datespan.enddate_param_utc
        }

    @property
    def columns(self):
        user = Column("Username", "user", column_type=SimpleColumn, calculate_fn=username)
        i_a = Column("Indicator A", "indicator_a")
        i_b = Column("Indicator B", "indicator_b")

        agg_c_d = AggregateColumn("C/D", combine_indicator,
                                  SumColumn("indicator_c"),
                                  SumColumn("indicator_d"))

        aggregate_cols = [
            i_a,
            i_b,
            agg_c_d
        ]

        if self.group_by:
            return [user] + aggregate_cols
        else:
            return aggregate_cols


def region_name(report, key):
    return report.regions[key]


def sub_region_name(report, key):
    return report.sub_regions[key]


class RegionTestReport(SqlTabularReport, DatespanMixin):
    name = "SQL Demo"
    slug = "sql_demo"
    field_classes = (DatespanField,)
    table_name = "region_report_data"

    @property
    @memoized
    def regions(self):
        return {"region1": "Cape Town", "region2": "Durban", 'region3': "Pretoria"}

    @property
    @memoized
    def sub_regions(self):
        return {"region1_a": "Ronderbosch", "region1_b": "Newlands",
                'region2_a': "Glenwood", 'region2_b': 'Morningside',
                'region3_a': "Arcadia", 'region3_b': 'Hatfield',
                }

    @property
    def filter_values(self):
        return {
            "startdate": self.datespan.startdate_param_utc,
            "enddate": self.datespan.enddate_param_utc
        }

    @property
    def columns(self):
        region = Column("Region", "region", column_type=SimpleColumn, calculate_fn=region_name)
        sub_region = Column("Sub Region", "sub_region", column_type=SimpleColumn, calculate_fn=sub_region_name)
        i_a = Column("Indicator A", "indicator_a")
        i_b = Column("Indicator B", "indicator_b")

        aggregate_cols = [
            i_a,
            i_b,
        ]

        if self.group_by:
            return [region, sub_region] + aggregate_cols
        else:
            return aggregate_cols