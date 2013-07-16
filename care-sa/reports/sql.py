from sqlagg.columns import *
from corehq.apps.reports.sqlreport import SqlTabularReport, DatabaseColumn
from corehq.apps.reports.standard import CustomProjectReport, DatespanMixin

MY_SLUGS = [
    'hiv_counseling'
]


class TestingAndCounseling(SqlTabularReport,
                           CustomProjectReport,
                           DatespanMixin):
    exportable = True
    emailable = True
    slug = 'tac_slug'
    name = "Testing and Counseling"
    table_name = "care-ihapc-live_CareSAFluff"

    fields = ['corehq.apps.reports.fields.DatespanField']

    @property
    def filters(self):
        return ["domain = :domain", "date between :startdate and :enddate"]

    @property
    def group_by(self):
        return ['user_id']

    @property
    def filter_values(self):
        return dict(domain=self.domain,
                    startdate=self.datespan.startdate_param_utc,
                    enddate=self.datespan.enddate_param_utc)

    @property
    def columns(self):
        user = DatabaseColumn("User", "user_id", column_type=SimpleColumn)
        columns = [user]

        for slug in MY_SLUGS:
            columns.append(DatabaseColumn(slug, '%s_total' % slug))

        return columns
