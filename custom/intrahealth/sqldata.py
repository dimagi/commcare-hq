from sqlagg.base import BaseColumn, AliasColumn
from sqlagg.columns import SumColumn, MaxColumn, SimpleColumn, CountColumn
from sqlagg.filters import AND, EQ, NOT, NOTEQ, BETWEEN
from corehq.apps.locations.models import Location
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn
from corehq.apps.reports.sqlreport import DatabaseColumn, SqlData, AggregateColumn, Column
from corehq.apps.reports.util import make_ctable_table_name


class BaseSqlData(SqlData):
    show_charts = False
    show_total = True

    @property
    def filters(self):
        filters = [BETWEEN("date", "startdate", "enddate")]
        if 'region_id' in self.config:
            filters.append(EQ("region_id", "region_id"))
        elif 'district_id' in self.config:
            filters.append(EQ("district_id", "district_id"))
        return filters

    @property
    def group_by(self):
        return []


class ConventureData(BaseSqlData):
    title = 'Converture'
    show_total = False
    table_name = 'fluff_CouvertureFluff'

    def percent_fn(self, x, y):
        return "%(p)s%%" % \
            {
                "p": (100 * int(y or 0) / (x or 1))
            }

    @property
    def group_by(self):
        if 'region_id' in self.config:
            return ['region_id']
        elif 'district_id' in self.config:
            return ['district_id']
        else:
            return []

    @property
    def columns(self):
        return [
            DatabaseColumn("No de PPS (number of PPS registered in that region)", MaxColumn('registered_total', alias='registered')),
            DatabaseColumn("No de PPS planifie (number of PPS planned)", MaxColumn('planned_total')),
            DatabaseColumn("No de PPS avec livrasion cet mois (number of PPS visited this month)",
                CountColumn('real_date_repeat',
                    alias="visited",
                    filters=self.filters + [NOTEQ("real_date_repeat", "visit")]
                )
            ),
            AggregateColumn("Taux de couverture (coverage ratio)", self.percent_fn,
                [AliasColumn('registered'), AliasColumn("visited")]),
            DatabaseColumn("No de PPS avec donnees soumises (number of PPS which submitted data)",
                 CountColumn('real_date_repeat',
                     alias="submitted",
                     filters=self.filters + [EQ("real_date_repeat", "visit")]
                 )),
            AggregateColumn("Exhaustivite des donnees", self.percent_fn,
                            [AliasColumn('visited'), AliasColumn('submitted')]),
        ]

class DispDesProducts(BaseSqlData):
    title = 'Taux de satisfaction de la commande de l\'operateur'
    table_name = 'test2'
    show_total = False

    @property
    def columns(self):
        return [
            DatabaseColumn("Incidents of Abuse", SumColumn('incidents_total')),
            ]