from sqlagg.base import AliasColumn
from sqlagg.columns import SumColumn, MaxColumn, SimpleColumn, CountColumn
from corehq.apps.commtrack.models import Product

from corehq.apps.reports.datatables import DataTablesColumn, DataTablesHeader
from corehq.apps.reports.sqlreport import DataFormatter, \
    TableDataFormat
from sqlagg.filters import EQ, NOTEQ, BETWEEN
from corehq.apps.reports.sqlreport import DatabaseColumn, SqlData, AggregateColumn
from django.utils.translation import ugettext as _

PRODUCT_NAMES = {
    u'diu': [u"diu"],
    u'jadelle': [u"jadelle"],
    u'depo-provera': [u"d\xe9po-provera", u"depo-provera"],
    u'microlut/ovrette': [u"microlut/ovrette"],
    u'microgynon/lof.': [u"microgynon/lof."],
    u'preservatif masculin': [u"pr\xe9servatif masculin", u"preservatif masculin"],
    u'preservatif feminin': [u"pr\xe9servatif f\xe9minin", u"preservatif feminin"],
    u'cu': [u"cu"],
    u'collier': [u"collier"]
}

class BaseSqlData(SqlData):
    show_charts = False
    show_total = True
    no_value = {'sort_key': 0, 'html': 0}

    def percent_fn(self, x, y):
        return "%(p)s%%" % \
            {
                "p": (100 * int(y or 0) / (x or 1))
            }

    @property
    def external_columns(self):
        return []

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

    @property
    def rows(self):
        formatter = DataFormatter(TableDataFormat(self.columns, no_value=self.no_value))
        return list(formatter.format(self.data, keys=self.keys, group_by=self.group_by))


class ConventureData(BaseSqlData):
    title = 'Converture'
    show_total = False
    table_name = 'fluff_CouvertureFluff'

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
    table_name = 'fluff_TauxDeSatisfactionFluff'
    show_total = False

    @property
    def group_by(self):
        group_by = []
        if 'region_id' in self.config:
            group_by.append('region_id')
        elif 'district_id' in self.config:
            group_by.append('district_id')
        group_by.append('product_name')
        return group_by

    @property
    def external_columns(self):
        return [DataTablesColumn(u"Quantit\xe9")]

    @property
    def rows(self):

        def row_in_names(row, names):
            if row in names:
                return True, names.index(row)+1
            else:
                for idx, val in enumerate(names):
                    if unicode(row).lower() in PRODUCT_NAMES[val]:
                        return True, idx+1
            return False, 0

        commandes = ['Comanndes']
        raux = ['Recu']
        taux = ['Taux']
        products = Product.by_domain(self.config['domain'])
        for product in products:
            commandes.append(0)
            raux.append(0)
            taux.append(0)
        names = []

        for product in products:
            names.append(unicode(product.name).lower())
        rows = super(DispDesProducts, self).rows
        for row in rows:
            exits, index = row_in_names(row[0], names)
            if exits:
                commandes[index] = row[1]
                raux[index] = row[2]
                print row[2]['html']
                taux[index] = "%d%%" % (100*row[2]['html']/row[1]['html'])
        return [commandes, raux, taux]

    @property
    def headers(self):
        columns = [DataTablesColumn('Quantity')]
        for product in Product.by_domain(self.config['domain']):
            columns.append(DataTablesColumn(product.name))
        return columns

    @property
    def columns(self):
        return [
            DatabaseColumn('Product Name', SimpleColumn('product_name')),
            DatabaseColumn("Commandes", SumColumn('commandes_total')),
            DatabaseColumn("Recu", SumColumn('recus_total'))
            ]

class FicheData(BaseSqlData):
    title = ''
    table_name = 'fluff_FicheFluff'
    show_total = True

    @property
    def group_by(self):
        return ['product_name', 'PPS_name']

    @property
    def columns(self):
        diff = lambda x, y: x - y
        return [
            DatabaseColumn(_("LISTE des PPS"), SimpleColumn('PPS_name')),
            DatabaseColumn(_("Consommation Reelle"), SumColumn('actual_consumption_total', alias='actual_consumption')),
            DatabaseColumn(_("Consommation Facturable"), SumColumn('billed_consumption_total', alias='billed_consumption')),
            AggregateColumn(_("Consommation Non Facturable"), diff,
                [AliasColumn('actual_consumption'), AliasColumn('billed_consumption')]),
        ]