from sqlagg.base import AliasColumn
from sqlagg.columns import SumColumn, MaxColumn, SimpleColumn, CountColumn, CountUniqueColumn
from corehq.apps.commtrack.models import Product

from corehq.apps.reports.datatables import DataTablesColumn, DataTablesHeader, DataTablesColumnGroup
from corehq.apps.reports.sqlreport import DataFormatter, \
    TableDataFormat, DictDataFormat, format_data
from sqlagg.filters import EQ, NOTEQ, BETWEEN, AND, GTE, LTE
from corehq.apps.reports.sqlreport import DatabaseColumn, SqlData, AggregateColumn
from django.utils.translation import ugettext as _
from dimagi.utils.decorators.memoized import memoized

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
    datatables = False
    show_charts = False
    show_total = True
    custom_total_calculate = False
    no_value = {'sort_key': 0, 'html': 0}
    fix_left_col = False

    def percent_fn(self, x, y):
        return "%(p)s%%" % \
            {
                "p": (100 * int(y or 0) / (x or 1))
            }

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
    slug = 'conventure'
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
        registered_column = "registered_total_for_region"
        if 'district_id' in self.config:
            registered_column = 'registered_total_for_district'
        return [
            DatabaseColumn("No de PPS (number of PPS registered in that region)", MaxColumn(registered_column, alias='registered')),
            DatabaseColumn("No de PPS planifie (number of PPS planned)", MaxColumn('planned_total')),
            DatabaseColumn("No de PPS avec livrasion cet mois (number of PPS visited this month)",
                CountUniqueColumn('location_id',
                    alias="visited",
                    filters=self.filters + [AND([GTE('real_date_repeat', "strsd"), LTE('real_date_repeat', "stred")])]
                )
            ),
            AggregateColumn("Taux de couverture (coverage ratio)", self.percent_fn,
                [AliasColumn('registered'), AliasColumn("visited")]),
            DatabaseColumn("No de PPS avec donnees soumises (number of PPS which submitted data)",
                 CountUniqueColumn('location_id',
                    alias="submitted",
                    filters=self.filters + [AND([GTE('real_date_repeat', "strsd"), LTE('real_date_repeat', "stred")])]
                )
            ),
            AggregateColumn("Exhaustivite des donnees", self.percent_fn,
                            [AliasColumn('visited'), AliasColumn('submitted')]),
        ]


class DispDesProducts(BaseSqlData):
    slug = 'products'
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
                taux[index] = "%d%%" % (100*row[2]['html']/(row[1]['html'] or 1))
        return [commandes, raux, taux]

    @property
    def headers(self):
        headers = DataTablesHeader(*[DataTablesColumn('Quantity')])
        for product in Product.by_domain(self.config['domain']):
            headers.add_column(DataTablesColumn(product.name))
        return headers

    @property
    def columns(self):

        return [
            DatabaseColumn('Product Name', SimpleColumn('product_name')),
            DatabaseColumn("Commandes", SumColumn('commandes_total')),
            DatabaseColumn("Recu", SumColumn('recus_total'))
            ]

class FicheData(BaseSqlData):
    title = ''
    table_name = 'fluff_IntraHealthFluff'
    show_total = True
    col_names = ['actual_consumption', 'billed_consumption', 'consommation-non-facturable']
    have_groups = True

    @property
    def group_by(self):
        return ['product_name', 'PPS_name']

    @property
    def columns(self):
        diff = lambda x, y: (x or 0) - (y or 0)
        return [
            DatabaseColumn(_("LISTE des PPS"), SimpleColumn('PPS_name')),
            DatabaseColumn(_("Consommation Reelle"), SumColumn('actual_consumption_total', alias='actual_consumption')),
            DatabaseColumn(_("Consommation Facturable"), SumColumn('billed_consumption_total', alias='billed_consumption')),
            AggregateColumn(_("Consommation Non Facturable"), diff,
                [AliasColumn('actual_consumption'), AliasColumn('billed_consumption')]),
        ]

class DateSource(BaseSqlData):
    title = ''
    table_name = 'fluff_RecapPassageFluff'

    @property
    def filters(self):
        filters = super(DateSource, self).filters
        if 'PPS_name' in self.config:
            filters.append(EQ("PPS_name", "PPS_name"))
        return filters

    @property
    def group_by(self):
        return ['date',]

    @property
    def columns(self):
        return [
            DatabaseColumn(_("Date"), SimpleColumn('date')),
        ]


class RecapPassageData(BaseSqlData):
    title = ''
    table_name = 'fluff_RecapPassageFluff'
    datatables = True
    show_total = True
    fix_left_col = True
    have_groups = False

    @property
    def slug(self):
        return 'recap_passage_%s' % self.config['startdate'].strftime("%Y-%m-%d")

    @property
    def title(self):
        return 'Recap Passage %s' % self.config['startdate'].strftime("%Y-%m-%d")

    @property
    def filters(self):
        filters = super(RecapPassageData, self).filters
        if 'PPS_name' in self.config:
            filters.append(EQ("PPS_name", "PPS_name"))
        return filters

    @property
    def group_by(self):
        return ['date', 'product_name',]

    @property
    def columns(self):
        diff = lambda x, y: (x or 0) - (y or 0)
        return [
            DatabaseColumn(_("Designations"), SimpleColumn('product_name')),
            DatabaseColumn(_("Stock apres derniere livraison"), SumColumn('product_old_stock_total')),
            DatabaseColumn(_("Stock disponible et utilisable a la livraison"), SumColumn('product_total_stock')),
            DatabaseColumn(_("Livraison"), SumColumn('product_livraison')),
            DatabaseColumn(_("Stock Total"), SumColumn('product_display_total_stock', alias='stock_total')),
            DatabaseColumn(_("Precedent"), SumColumn('product_old_stock_pps')),
            DatabaseColumn(_("Recu hors entrepots mobiles"), SumColumn('product_outside_receipts_amount')),
            AggregateColumn(_("Non Facturable"), diff,
                [AliasColumn('aconsumption'), AliasColumn("bconsumption")]),
            DatabaseColumn(_("Facturable"), SumColumn('product_billed_consumption', alias='bconsumption')),
            DatabaseColumn(_("Reelle"), SumColumn('product_actual_consumption', alias='aconsumption')),
            DatabaseColumn("Stock Total", AliasColumn('stock_total')),
            DatabaseColumn("PPS Restant", SumColumn('product_pps_restant'))
        ]

class ConsommationData(BaseSqlData):
    slug = 'consommation'
    title = 'Consommation'
    table_name = 'fluff_IntraHealthFluff'
    show_charts = True
    chart_x_label = 'Products'
    chart_y_label = 'Number of consumption'
    datatables = True
    fix_left_col = True
    col_names = ['actual_consumption_total']
    have_groups = False

    @property
    def group_by(self):
        group_by = ['product_name']
        if 'region_id' in self.config:
            group_by.append('district_name')
        else:
            group_by.append('PPS_name')

        return group_by

    @property
    def columns(self):
        columns = []
        if 'region_id' in self.config:
            columns.append(DatabaseColumn(_("District"), SimpleColumn('district_name')))
        else:
            columns.append(DatabaseColumn(_("PPS"), SimpleColumn('PPS_name')))

        columns.append(DatabaseColumn(_("Consumption"), SumColumn('actual_consumption_total')))
        return columns


class TauxConsommationData(BaseSqlData):
    slug = 'taux_consommation'
    title = 'Taux de Consommation'
    table_name = 'fluff_IntraHealthFluff'
    datatables = True
    custom_total_calculate = True
    fix_left_col = True
    col_names = ['consumption', 'stock', 'taux-consommation']
    sum_cols = ['consumption', 'stock']
    have_groups = True

    @property
    def group_by(self):
        group_by = ['date']
        if 'region_id' in self.config:
            group_by.extend(['district_name', 'PPS_name'])
        else:
            group_by.append('PPS_name')
        group_by.extend(['product_name', 'consumption', 'stock'])
        return group_by

    @property
    def columns(self):
        columns = []
        if 'region_id' in self.config:
            columns.append(DatabaseColumn(_("District"), SimpleColumn('district_name')))
        else:
            columns.append(DatabaseColumn(_("PPS"), SimpleColumn('PPS_name')))

        columns.append(DatabaseColumn(_("Consommation reelle"), SimpleColumn('actual_consumption_total', alias="consumption"), format_fn=format_data))
        columns.append(DatabaseColumn(_("Stock apres derniere livraison"), SimpleColumn('stock_total', alias="stock"), format_fn=format_data))
        columns.append(AggregateColumn(_("Taux consommation"), self.percent_fn,
                                   [AliasColumn('stock'), AliasColumn('consumption')]))
        return columns

    def calculate_total_row(self, rows):
        total_row = []
        if len(rows) > 0:
            num_cols = len(rows[0])
            for i in range(num_cols):
                if i != 0 and i % 3 == 0:
                    cp = total_row[-2:]
                    total_row.append("%s%%" % (100 * int(cp[0] or 0) / (cp[1] or 1)))
                else:
                    colrows = [cr[i] for cr in rows if isinstance(cr[i], dict)]
                    columns = [r.get('sort_key') for r in colrows if isinstance(r.get('sort_key'), (int, long))]
                    if len(columns):
                        total_row.append(reduce(lambda x, y: x + y, columns, 0))
                    else:
                        total_row.append('')

        return total_row

class NombreData(BaseSqlData):
    slug = 'nombre'
    title = 'Nombre de mois de stock disponibles et utilisables aux PPS'
    table_name = 'fluff_IntraHealthFluff'
    datatables = True
    custom_total_calculate = True
    fix_left_col = True
    col_names = ['quantity', 'cmm', 'nombre-mois-stock-disponible-et-utilisable']
    sum_cols = ['quantity', 'cmm']
    have_groups = True

    @property
    def group_by(self):
        group_by = ['date']
        if 'region_id' in self.config:
            group_by.extend(['district_name', 'PPS_name'])
        else:
            group_by.append('PPS_name')
        group_by.extend(['product_name', 'quantity', 'cmm'])

        return group_by

    @property
    def columns(self):
        div = lambda x, y: "%0.3f" % (x / (float(y) or 1.0))
        columns = []
        if 'region_id' in self.config:
            columns.append(DatabaseColumn(_("District"), SimpleColumn('district_name')))
        else:
            columns.append(DatabaseColumn(_("PPS"), SimpleColumn('PPS_name')))

        columns.append(DatabaseColumn(_("Quantite produits entreposes au PPS"), SimpleColumn('quantity_total', alias="quantity"), format_fn=format_data))
        columns.append(DatabaseColumn(_("CMM"), SimpleColumn('cmm_total', alias="cmm"), format_fn=format_data))
        columns.append(AggregateColumn(_("Nombre mois stock disponible et utilisable"), div,
                                   [AliasColumn('quantity'), AliasColumn('cmm')]))
        return columns

    def calculate_total_row(self, rows):
        total_row = []
        if len(rows) > 0:
            num_cols = len(rows[0])
            for i in range(num_cols):
                if i != 0 and i % 3 == 0:
                    cp = total_row[-2:]
                    total_row.append("%0.3f" % (cp[0] / (float(cp[1]) or 1.0)))
                else:
                    colrows = [cr[i] for cr in rows if isinstance(cr[i], dict)]
                    columns = [r.get('sort_key') for r in colrows if isinstance(r.get('sort_key'), (int, long))]
                    if len(columns):
                        total_row.append(reduce(lambda x, y: x + y, columns, 0))
                    else:
                        total_row.append('')

        return total_row
