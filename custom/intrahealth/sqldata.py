# coding=utf-8
from sqlagg.base import AliasColumn, QueryMeta, CustomQueryColumn
from sqlagg.columns import SumColumn, MaxColumn, SimpleColumn, CountColumn, CountUniqueColumn, MeanColumn
from sqlalchemy.sql.expression import alias
from corehq.apps.locations.models import SQLLocation
from corehq.apps.products.models import SQLProduct

from corehq.apps.reports.datatables import DataTablesColumn, DataTablesHeader
from corehq.apps.reports.sqlreport import DataFormatter, \
    TableDataFormat, calculate_total_row
from sqlagg.filters import EQ, BETWEEN, AND, GTE, LTE, NOT, IN
from corehq.apps.reports.sqlreport import DatabaseColumn, SqlData, AggregateColumn
from django.utils.translation import ugettext as _
from sqlalchemy import select
from dimagi.utils.parsing import json_format_date

PRODUCT_NAMES = {
    u'diu': [u"diu"],
    u'jadelle': [u"jadelle"],
    u'depo-provera': [u"d\xe9po-provera", u"depo-provera"],
    u'd\xe9po-provera': [u"d\xe9po-provera", u"depo-provera"],
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
        return "%(p).2f%%" % \
            {
                "p": (100 * float(y or 0) / float(x or 1))
            }

    def format_data_and_cast_to_float(self, value):
        return {"html": round(value, 2), "sort_key": round(value, 2)} if value is not None else value

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

    # this is copy/paste from the
    # https://github.com/dimagi/commcare-hq/blob/master/corehq/apps/reports/sqlreport.py#L383
    # we added possibility to sum Float values
    def calculate_total_row(self, rows):
        total_row = []
        if len(rows) > 0:
            num_cols = len(rows[0])
            for i in range(num_cols):
                colrows = [cr[i] for cr in rows if isinstance(cr[i], dict)]
                columns = [r.get('sort_key') for r in colrows if isinstance(r.get('sort_key'), (int, long, float))]
                if len(columns):
                    total_row.append(reduce(lambda x, y: x + y, columns, 0))
                else:
                    total_row.append('')
        return total_row


class ConventureData(BaseSqlData):
    slug = 'conventure'
    title = 'Converture'
    show_total = False
    table_name = 'fluff_CouvertureFluff'
    custom_total_calculate = True

    @property
    def filters(self):
        #We have to filter data by real_date_repeat not date(first position in filters list).
        #Filtering is done directly in columns method(CountUniqueColumn).
        filters = super(ConventureData, self).filters
        filters.append(AND([GTE('real_date_repeat', "strsd"), LTE('real_date_repeat', "stred")]))
        if 'archived_locations' in self.config:
            filters.append(NOT(IN('location_id', 'archived_locations')))
        return filters[1:]

    @property
    def group_by(self):
        group_by = []

        if 'region_id' in self.config:
            group_by.append('region_id')
        elif 'district_id' in self.config:
            group_by.append('district_id')

        if self.config['startdate'].month != self.config['enddate'].month:
            group_by.append('month')
        return group_by

    @property
    def columns(self):
        registered_column = "registered_total_for_region"
        if 'district_id' in self.config:
            registered_column = 'registered_total_for_district'
        columns = [
            DatabaseColumn("No de PPS (number of PPS registered in that region)",
                           MaxColumn(registered_column, alias='registered')),
            DatabaseColumn("No de PPS planifie (number of PPS planned)", MaxColumn('planned_total')),
            DatabaseColumn("No de PPS avec livrasion cet mois (number of PPS visited this month)",
                           CountUniqueColumn('location_id', alias="visited")
                           ),
            AggregateColumn("Taux de couverture (coverage ratio)", self.percent_fn,
                            [AliasColumn('registered'), AliasColumn("visited")]),
            DatabaseColumn("No de PPS avec donnees soumises (number of PPS which submitted data)",
                           CountUniqueColumn('location_id', alias="submitted")
                           ),
            AggregateColumn("Exhaustivite des donnees", self.percent_fn,
                            [AliasColumn('visited'), AliasColumn('submitted')]),
        ]
        if self.config['startdate'].month != self.config['enddate'].month:
            columns.insert(0, DatabaseColumn('Mois', SimpleColumn('month')))
            self.show_total = True
        return columns

    @property
    def rows(self):
        formatter = DataFormatter(TableDataFormat(self.columns, no_value=self.no_value))
        rows = list(formatter.format(self.data, keys=self.keys, group_by=self.group_by))

        #Months are displayed in chronological order
        if 'month' in self.group_by:
            from custom.intrahealth.reports import get_localized_months
            return sorted(rows, key=lambda row: get_localized_months().index(row[0]))

        return rows

    def calculate_total_row(self, rows):
        total_row = super(ConventureData, self).calculate_total_row(rows)
        if len(total_row) != 0:
            #two cell's are recalculated because the summation of percentage gives us bad values
            total_row[4] = "%.0f%%" % (total_row[3] * 100 / float(total_row[1]))
            total_row[-1] = "%.0f%%" % (total_row[5] * 100 / float(total_row[3]))
        return total_row


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
        group_by.append('product_code')
        return group_by

    @property
    def rows(self):

        def row_in_names(row, names):
            if row in names:
                return True, names.index(row)+1
            else:
                for idx, val in enumerate(names):
                    if unicode(row).lower() in PRODUCT_NAMES.get(val, []):
                        return True, idx+1
            return False, 0

        commandes = ['Comanndes']
        raux = ['Recu']
        taux = ['Taux']
        products = SQLProduct.objects.filter(domain=self.config['domain'], is_archived=False)
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
        for product in SQLProduct.objects.filter(domain=self.config['domain'], is_archived=False):
            headers.add_column(DataTablesColumn(product.name))
        return headers

    @property
    def columns(self):
        return [
            DatabaseColumn('Product Name', SimpleColumn('product_code'),
                           format_fn=lambda code: SQLProduct.objects.get(code=code, domain=self.config['domain'],
                                                                         is_archived=False).name),
            DatabaseColumn("Commandes", SumColumn('commandes_total')),
            DatabaseColumn("Recu", SumColumn('recus_total'))
        ]


class TauxDeRuptures(BaseSqlData):
    slug = 'taux_de_ruptures'
    title = u'Disponibilité des Produits - Taux des Ruptures de Stock'
    table_name = 'fluff_IntraHealthFluff'
    col_names = ['total_stock_total']
    have_groups = False
    custom_total_calculate = True

    @property
    def group_by(self):
        group_by = ['product_code']
        if 'region_id' in self.config:
            group_by.append('district_name')
        else:
            group_by.append('PPS_name')

        return group_by

    @property
    def filters(self):
        filter = super(TauxDeRuptures, self).filters
        filter.append("total_stock_total = 0")
        if 'archived_locations' in self.config:
            filter.append(NOT(IN('location_id', 'archived_locations')))
        return filter

    @property
    def columns(self):
        columns = []
        if 'region_id' in self.config:
            columns.append(DatabaseColumn(_("District"), SimpleColumn('district_name')))
        else:
            columns.append(DatabaseColumn(_("PPS"), SimpleColumn('PPS_name')))

        columns.append(DatabaseColumn(_("Stock total"), CountColumn('total_stock_total')))
        return columns

    def calculate_total_row(self, rows):
        conventure = ConventureData(self.config)
        if self.config['startdate'].month != self.config['enddate'].month:
            conventure_data_rows = conventure.calculate_total_row(conventure.rows)
            total = conventure_data_rows[3] if conventure_data_rows else 0
        else:
            conventure_data_rows = conventure.rows
            total = conventure_data_rows[0][2]["html"] if conventure_data_rows else 0

        for row in rows:
            row.append(dict(sort_key=1L if any([x["sort_key"] for x in row[1:]]) else 0L,
                            html=1L if any([x["sort_key"] for x in row[1:]]) else 0L))

        total_row = list(calculate_total_row(rows))

        taux_rapture_row = ["(%s/%s) %s" % (x, total, self.percent_fn(total, x)) for x in total_row]

        if total_row:
            total_row[0] = 'Total'

        if taux_rapture_row:
            taux_rapture_row[0] = 'Taux rupture'

        rows.append(total_row)

        return taux_rapture_row


class FicheData(BaseSqlData):
    title = ''
    table_name = 'fluff_IntraHealthFluff'
    show_total = True
    col_names = ['actual_consumption', 'billed_consumption', 'consommation-non-facturable']
    have_groups = True

    @property
    def filters(self):
        filters = super(FicheData, self).filters
        if 'archived_locations' in self.config:
            filters.append(NOT(IN('location_id', 'archived_locations')))
        return filters

    @property
    def group_by(self):
        return ['product_code', 'PPS_name']

    @property
    def columns(self):
        diff = lambda x, y: (x or 0) - (y or 0)
        return [
            DatabaseColumn(_("LISTE des PPS"), SimpleColumn('PPS_name')),
            DatabaseColumn(_("Consommation Reelle"),
                           SumColumn('actual_consumption_total', alias='actual_consumption')),
            DatabaseColumn(_("Consommation Facturable"),
                           SumColumn('billed_consumption_total', alias='billed_consumption')),
            AggregateColumn(_("Consommation Non Facturable"), diff,
                            [AliasColumn('actual_consumption'), AliasColumn('billed_consumption')]),
        ]

class PPSAvecDonnees(BaseSqlData):
    slug = 'pps_avec_donnees'
    title = 'PPS Avec Données'
    table_name = 'fluff_CouvertureFluff'
    col_names = ['location_id']
    have_groups = False

    @property
    def filters(self):
        filters = super(PPSAvecDonnees, self).filters
        filters.append(AND([GTE('real_date_repeat', "strsd"), LTE('real_date_repeat', "stred")]))
        if 'archived_locations' in self.config:
            filters.append(NOT(IN('location_id', 'archived_locations')))
        return filters[1:]

    @property
    def group_by(self):
        group_by = []
        if 'region_id' in self.config:
            group_by.append('district_name')
        else:
            group_by.append('pps_name')
        return group_by

    @property
    def columns(self):
        columns = []
        if 'region_id' in self.config:
            columns.append(DatabaseColumn(_("District"), SimpleColumn('district_name')))
        else:
            columns.append(DatabaseColumn(_("PPS"), SimpleColumn('pps_name')))

        columns.append(DatabaseColumn(_(u"PPS Avec Données Soumises"),
                                      CountUniqueAndSumCustomColumn('location_id'),
                                      format_fn=lambda x: {'sort_key': long(x), 'html': long(x)})
        )
        return columns

    @property
    def rows(self):
        rows = super(PPSAvecDonnees, self).rows
        if 'district_id' in self.config:
            locations_included = [row[0] for row in rows]
        else:
            return rows
        all_locations = SQLLocation.objects.get(
            location_id=self.config['district_id']
        ).get_children().exclude(is_archived=True).values_list('name', flat=True)
        locations_not_included = set(all_locations) - set(locations_included)
        return rows + [[location, {'sort_key': 0L, 'html': 0L}] for location in locations_not_included]


class DateSource(BaseSqlData):
    title = ''
    table_name = 'fluff_RecapPassageFluff'

    @property
    def filters(self):
        filters = super(DateSource, self).filters
        if 'location_id' in self.config:
            filters.append(EQ('location_id', 'location_id'))
        filters.append(NOT(EQ('product_code', 'empty_prd_code')))
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
    show_total = False
    fix_left_col = True
    have_groups = False

    @property
    def slug(self):
        return 'recap_passage_%s' % json_format_date(self.config['startdate'])

    @property
    def title(self):
        return 'Recap Passage %s' % json_format_date(self.config['startdate'])

    @property
    def filters(self):
        filters = super(RecapPassageData, self).filters
        if 'location_id' in self.config:
            filters.append(EQ("location_id", "location_id"))
        filters.append(NOT(EQ('product_code', 'empty_prd_code')))
        return filters

    @property
    def group_by(self):
        return ['date', 'product_code']

    @property
    def columns(self):
        diff = lambda x, y: (x or 0) - (y or 0)
        return [
            DatabaseColumn(_("Designations"), SimpleColumn('product_code'),
                           format_fn=lambda code: SQLProduct.objects.get(code=code, domain=self.config['domain'],
                                                                         is_archived=False).name),
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
            DatabaseColumn("PPS Restant", SumColumn('product_pps_restant')),
            DatabaseColumn("Pertes et Adjustement", SumColumn('product_loss_amt'))
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
    def filters(self):
        filters = super(ConsommationData, self).filters
        if 'archived_locations' in self.config:
            filters.append(NOT(IN('location_id', 'archived_locations')))
        return filters

    @property
    def group_by(self):
        group_by = ['product_code']
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
    def filters(self):
        filters = super(TauxConsommationData, self).filters
        if 'archived_locations' in self.config:
            filters.append(NOT(IN('location_id', 'archived_locations')))
        return filters

    @property
    def group_by(self):
        group_by = []
        if 'region_id' in self.config:
            group_by.extend(['district_name', 'PPS_name'])
        else:
            group_by.append('PPS_name')
        group_by.append('product_code')
        return group_by

    @property
    def columns(self):
        columns = []
        if 'region_id' in self.config:
            columns.append(DatabaseColumn(_("District"), SimpleColumn('district_name')))
        else:
            columns.append(DatabaseColumn(_("PPS"), SimpleColumn('PPS_name')))

        columns.append(DatabaseColumn(_("Consommation reelle"),
                                      MeanColumn('actual_consumption_total', alias="consumption"),
                                      format_fn=self.format_data_and_cast_to_float))
        columns.append(DatabaseColumn(_("Stock apres derniere livraison"),
                                      MeanColumn('stock_total', alias="stock"),
                                      format_fn=self.format_data_and_cast_to_float))
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
    def filters(self):
        filters = super(NombreData, self).filters
        if 'archived_locations' in self.config:
            filters.append(NOT(IN('location_id', 'archived_locations')))
        return filters

    @property
    def group_by(self):
        group_by = []
        if 'region_id' in self.config:
            group_by.extend(['district_name', 'PPS_name'])
        else:
            group_by.append('PPS_name')
        group_by.append('product_code')

        return group_by

    @property
    def columns(self):
        div = lambda x, y: "%0.3f" % (float(x) / (float(y) or 1.0))
        columns = []
        if 'region_id' in self.config:
            columns.append(DatabaseColumn(_("District"), SimpleColumn('district_name')))
        else:
            columns.append(DatabaseColumn(_("PPS"), SimpleColumn('PPS_name')))

        columns.append(DatabaseColumn(_("Quantite produits entreposes au PPS"),
                                      MeanColumn('quantity_total', alias="quantity"),
                                      format_fn=self.format_data_and_cast_to_float))
        columns.append(DatabaseColumn(_("CMM"), MeanColumn('cmm_total', alias="cmm"),
                                      format_fn=self.format_data_and_cast_to_float))
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
                    total_row.append("%0.3f" % (float(cp[0]) / (float(cp[1]) or 1.0)))
                else:
                    colrows = [cr[i] for cr in rows if isinstance(cr[i], dict)]
                    columns = [r.get('sort_key') for r in colrows if isinstance(r.get('sort_key'), (int, long, float))]
                    if len(columns):
                        total_row.append(reduce(lambda x, y: x + y, columns, 0))
                    else:
                        total_row.append('')

        return total_row


class GestionDeLIPMTauxDeRuptures(TauxDeRuptures):
    table_name = 'fluff_TauxDeRuptureFluff'
    title = u'Gestion de l`IPM - Taux des Ruptures de Stock'

    @property
    def filters(self):
        return super(TauxDeRuptures, self).filters

    @property
    def columns(self):
        columns = []
        if 'region_id' in self.config:
            columns.append(DatabaseColumn(_("District"), SimpleColumn('district_name')))
        else:
            columns.append(DatabaseColumn(_("PPS"), SimpleColumn('PPS_name')))

        columns.append(DatabaseColumn(_("Stock total"), SumColumn('total_stock_total')))
        return columns


class DureeData(BaseSqlData):
    slug = 'duree'
    custom_total_calculate = True
    title = u'Durée moyenne des retards de livraison'
    table_name = 'fluff_LivraisonFluff'
    have_groups = False
    col_names = ['duree_moyenne_livraison_total']

    @property
    def group_by(self):
        return ['district_name']

    @property
    def columns(self):
        columns = [DatabaseColumn(_("District"), SimpleColumn('district_name')),
                   DatabaseColumn(_(u"Retards de livraison (jours)"),
                                  SumAndAvgGCustomColumn('duree_moyenne_livraison_total'),
                                  format_fn=lambda x: {'sort_key': float(x), 'html': float(x)})]
        return columns

    def calculate_total_row(self, rows):
        total_row = super(DureeData, self).calculate_total_row(rows)
        if total_row:
            total_row[0] = 'Moyenne Region'
            total_row[-1] = "%.2f" % (total_row[-1] / float(len(self.rows)))
        return total_row


class RecouvrementDesCouts(BaseSqlData):
    slug = 'recouvrement'
    custom_total_calculate = True
    title = u'Recouvrement des côuts - Taxu de Recouvrement'

    table_name = 'fluff_RecouvrementFluff'
    have_groups = False
    col_names = ['district_name', 'payments_amount_paid', 'payments_amount_to_pay',
                 'payments_in_30_days', 'payments_in_3_months', 'payments_in_year']

    @property
    def group_by(self):
        return ['district_name']

    @property
    def filters(self):
        filters = super(RecouvrementDesCouts, self).filters
        return filters

    @property
    def columns(self):
        columns = [DatabaseColumn(_("District"), SimpleColumn('district_name'))]
        columns.append(DatabaseColumn(_(u"Montant dû"), SumColumn('payments_amount_to_pay')))
        columns.append(DatabaseColumn(_(u"Montant payé"), SumColumn('payments_amount_paid')))
        columns.append(DatabaseColumn(_(u"Payé dans le 30 jours"), SumColumn('payments_in_30_days')))
        columns.append(DatabaseColumn(_(u"Payé dans le 3 mois"), SumColumn('payments_in_3_months')))
        columns.append(DatabaseColumn(_(u"Payé dans l`annèe"), SumColumn('payments_in_year')))
        return columns

    def calculate_total_row(self, rows):
        total_row = super(RecouvrementDesCouts, self).calculate_total_row(rows)
        if total_row:
            total_row[0] = 'Total Region'
        return total_row


class IntraHealthQueryMeta(QueryMeta):

    def __init__(self, table_name, filters, group_by, key):
        self.key = key
        super(IntraHealthQueryMeta, self).__init__(table_name, filters, group_by)

    def execute(self, metadata, connection, filter_values):
        return connection.execute(self._build_query(filter_values)).fetchall()


class SumAndAvgQueryMeta(IntraHealthQueryMeta):

    def _build_query(self, filter_values):

        sum_query = alias(select(self.group_by + ["SUM(%s) AS sum_col" % self.key] + ['month'],
                                 group_by=self.group_by + ['month'],
                                 whereclause=' AND '.join([f.build_expression() for f in self.filters]),
                                 from_obj="\"" + self.table_name + "\""
                                 ), name='s')

        return select(self.group_by + ['AVG(s.sum_col) AS %s' % self.key],
                      group_by=self.group_by,
                      from_obj=sum_query
                      ).params(filter_values)


class CountUniqueAndSumQueryMeta(IntraHealthQueryMeta):

    def _build_query(self, filter_values):

        count_uniq = alias(select(self.group_by + ["COUNT(DISTINCT(%s)) AS count_unique" % self.key],
                                  group_by=self.group_by + ['month'],
                                  whereclause=' AND '.join([f.build_expression() for f in self.filters]),
                                  from_obj="\"" + self.table_name + "\""
                                  ), name='cq')

        return select(self.group_by + ['SUM(cq.count_unique) AS %s' % self.key],
                      group_by=self.group_by,
                      from_obj=count_uniq
                      ).params(filter_values)


class IntraHealthCustomColumn(CustomQueryColumn):

    def get_query_meta(self, default_table_name, default_filters, default_group_by):
        table_name = self.table_name or default_table_name
        filters = self.filters or default_filters
        group_by = self.group_by or default_group_by
        return self.query_cls(table_name, filters, group_by, self.key)

class SumAndAvgGCustomColumn(IntraHealthCustomColumn):
    query_cls = SumAndAvgQueryMeta
    name = 'sum_and_avg'


class CountUniqueAndSumCustomColumn(IntraHealthCustomColumn):
    query_cls = CountUniqueAndSumQueryMeta
    name = 'count_unique_and_sum'
