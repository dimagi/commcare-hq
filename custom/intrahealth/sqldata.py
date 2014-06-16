from sqlagg.base import AliasColumn
from sqlagg.columns import SumColumn, MaxColumn, SimpleColumn, CountColumn
from corehq.apps.commtrack.models import Product

from corehq.apps.reports.datatables import DataTablesColumn, DataTablesHeader, DataTablesColumnGroup
from corehq.apps.reports.sqlreport import DataFormatter, \
    TableDataFormat, DictDataFormat
from sqlagg.filters import EQ, NOTEQ, BETWEEN
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

class RecapPassageData(BaseSqlData):
    title = ''
    table_name = 'fluff_RecapPassageFluff'
    show_total = True

    @property
    def filters(self):
        filters = super(RecapPassageData, self).filters
        if 'PPS_name' in self.config:
            filters.append(EQ("PPS_name", "PPS_name"))
        return filters

    @property
    def group_by(self):
        return ['product_name',]

    @property
    def columns(self):
        diff = lambda x, y: x - y
        return [
            DatabaseColumn(_("Designations"), SimpleColumn('product_name')),
            DatabaseColumn(_("Stock apres derniere livraison"), SumColumn('product_old_stock_total')),
            DatabaseColumn(_("Stock disponible et utilisable a la livraison"), SumColumn('product_total_stock')),
            DatabaseColumn(_("Livraison"), SumColumn('product_livraison')),
            DatabaseColumn(_("Stock Total (disponible + livree)"), SumColumn('product_display_total_stock')),
            DatabaseColumn(_("Precedent"), SumColumn('product_old_stock_pps')),
            DatabaseColumn(_("Recu hors entrepots mobiles"), SumColumn('product_outside_receipts_amount')),
            AggregateColumn(_("Non Facturable"), diff,
                [AliasColumn('aconsumption'), AliasColumn("bconsumption")]),
            DatabaseColumn(_("Facturable"), SumColumn('product_billed_consumption', alias='bconsumption')),
            DatabaseColumn(_("Reelle"), SumColumn('product_actual_consumption', alias='aconsumption')),
            DatabaseColumn(_("PPS Restant"), SumColumn('product_pps_restant'))
        ]

class ConsommationData(BaseSqlData):
    slug = 'consommation'
    title = 'Consommation'
    table_name = 'fluff_ConsommationFluff'
    show_charts = True
    chart_x_label = 'Products'
    chart_y_label = 'Number of consumption'
    products = []
    datatables = True

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

        columns.append(DatabaseColumn(_("Consumption"), SumColumn('consumption_total')))
        return columns

    @property
    def headers(self):
        header = DataTablesHeader()
        columns = self.columns
        header.add_column(columns[0].data_tables_column)
        self.products = sorted(list(set(zip(*self.data.keys())[0])))
        for product in self.products:
            header.add_column(DataTablesColumn(product))
        return header

    @property
    def rows(self):
        data = self.data
        locs = sorted(list(set(zip(*data.keys())[1])))
        rows = []

        formatter = DataFormatter(DictDataFormat(self.columns, no_value=self.no_value))
        data = dict(formatter.format(self.data, keys=self.keys, group_by=self.group_by))
        for loc in locs:
            row = [loc]
            for prd in self.products:
                if (prd, loc) in data:
                    product = data[(prd, loc)]
                    row.append(product['consumption_total'])
                else:
                    row.append(self.no_value)
            rows.append(row)
        return rows

class TauxConsommationData(BaseSqlData):
    slug = 'taux_consommation'
    title = 'Taux de Consommation'
    table_name = 'fluff_TauxConsommationFluff'
    products = []
    datatables = True
    custom_total_calculate = True

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

        columns.append(DatabaseColumn(_("Consommation reelle"), SumColumn('consumption_total', alias="consumption")))
        columns.append(DatabaseColumn(_("Stock apres derniere livraison"), SumColumn('stock_total', alias="stock")))
        columns.append(AggregateColumn(_("Taux consommation"), self.percent_fn,
                                   [AliasColumn('stock'), AliasColumn('consumption')]))
        return columns

    @property
    def headers(self):
        header = DataTablesHeader()
        columns = self.columns
        header.add_column(DataTablesColumnGroup('', columns[0].data_tables_column))
        self.products = sorted(list(set(zip(*self.data.keys())[0])))
        for prd in self.products:
            header.add_column(DataTablesColumnGroup(prd,
                                                    *[columns[j].data_tables_column for j in xrange(1, len(columns))]))

        return header

    @property
    @memoized
    def rows(self):
        data = self.data
        ppss = sorted(list(set(zip(*data.keys())[1])))
        rows = []

        formatter = DataFormatter(DictDataFormat(self.columns, no_value=self.no_value))
        data = dict(formatter.format(self.data, keys=self.keys, group_by=self.group_by))
        for pps in ppss:
            row = [pps]
            for prd in self.products:
                if (prd, pps) in data:
                    product = data[(prd, pps)]
                    row += [product['consumption'], product['stock'], product['taux-consommation']]
                else:
                    row += [self.no_value, self.no_value, self.no_value]
            rows.append(row)
        return rows

    @property
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
    table_name = 'fluff_NombreFluff'
    products = []
    datatables = True
    custom_total_calculate = True

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
        div = lambda x, y: "%0.3f" % (x / (float(y) or 1.0))
        columns = []
        if 'region_id' in self.config:
            columns.append(DatabaseColumn(_("District"), SimpleColumn('district_name')))
        else:
            columns.append(DatabaseColumn(_("PPS"), SimpleColumn('PPS_name')))

        columns.append(DatabaseColumn(_("Quantite produits entreposes au PPS"), SumColumn('quantity_total', alias="quantity")))
        columns.append(DatabaseColumn(_("CMM"), SumColumn('cmm_total', alias="cmm")))
        columns.append(AggregateColumn(_("Nombre mois stock disponible et utilisable"), div,
                                   [AliasColumn('quantity'), AliasColumn('cmm')]))
        return columns

    @property
    def headers(self):
        header = DataTablesHeader()
        columns = self.columns
        header.add_column(DataTablesColumnGroup('', columns[0].data_tables_column))
        self.products = sorted(list(set(zip(*self.data.keys())[0])))
        for prd in self.products:
            header.add_column(DataTablesColumnGroup(prd,
                                                    *[columns[j].data_tables_column for j in xrange(1, len(columns))]))

        return header

    @property
    def rows(self):
        data = self.data
        ppss = sorted(list(set(zip(*data.keys())[1])))
        rows = []

        formatter = DataFormatter(DictDataFormat(self.columns, no_value=self.no_value))
        data = dict(formatter.format(self.data, keys=self.keys, group_by=self.group_by))
        for pps in ppss:
            row = [pps]
            for prd in self.products:
                if (prd, pps) in data:
                    product = data[(prd, pps)]
                    row += [product['quantity'], product['cmm'], product['nombre-mois-stock-disponible-et-utilisable']]
                else:
                    row += [self.no_value, self.no_value, self.no_value]
            rows.append(row)
        return rows

    @property
    def calculate_total_row(self, rows):
        total_row = []
        if len(rows) > 0:
            num_cols = len(rows[0])
            for i in range(num_cols):
                colrows = [cr[i] for cr in rows if isinstance(cr[i], dict)]
                columns = [r.get('sort_key') for r in colrows if isinstance(r.get('sort_key'), (int, long))]
                if len(columns):
                    total_row.append(reduce(lambda x, y: x + y, columns, 0))
                else:
                    total_row.append('')

        return total_row
