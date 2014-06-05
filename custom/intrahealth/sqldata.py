from sqlagg.columns import SumColumn, MaxColumn
from corehq.apps.reports.sqlreport import DatabaseColumn, SqlData
from corehq.apps.reports.util import make_ctable_table_name


class BaseSqlData(SqlData):

    @property
    def filters(self):
        return []

    @property
    def group_by(self):
        return []


class ConventureData(BaseSqlData):
    title = 'Converture'
    chart_x_label = ''
    chart_y_label = ''
    table_name = 'test'

    @property
    def columns(self):
        return [
            DatabaseColumn("No de PPS (number of PPS registered in that region)", MaxColumn('registered_total')),
            DatabaseColumn("No de PPS planifie (number of PPS planned)", SumColumn('planned_total')),
            DatabaseColumn("No de PPS avec livrasion cet mois (number of PPS visited this month)", SumColumn('visited_total')),
            DatabaseColumn("Taux de couverture (coverage ratio)", 0),
            DatabaseColumn("No de PPS avec donnees soumises (number of PPS which submitted data)", SumColumn('submitted_total')),
            DatabaseColumn("Exhaustivite des donnees", 0),

        ]

class DispDesProducts(BaseSqlData):
    title = 'Taux de satisfaction de la commande de l\'operateur'
    chart_x_label = ''
    chart_y_label = ''
    table_name = 'test2'

    @property
    def columns(self):
        return [
            DatabaseColumn("Incidents of Abuse", SumColumn('incidents_total')),
            ]