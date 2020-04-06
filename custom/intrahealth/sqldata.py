import datetime
from decimal import Decimal

import sqlalchemy
from sqlagg.base import AliasColumn, QueryMeta, CustomQueryColumn
from sqlagg.columns import SumColumn, MaxColumn, SimpleColumn, CountColumn, CountUniqueColumn, MeanColumn, \
    MonthColumn
from collections import defaultdict

from corehq.apps.locations.models import SQLLocation, get_location
from corehq.apps.products.models import SQLProduct
from corehq.apps.reports.datatables import DataTablesColumn, DataTablesHeader, DataTablesColumnGroup
from corehq.apps.reports.sqlreport import DataFormatter, \
    TableDataFormat, calculate_total_row
from corehq.apps.userreports.models import StaticDataSourceConfiguration, get_datasource_config
from corehq.apps.userreports.util import get_table_name

from custom.intrahealth import PRODUCT_NAMES as INIT_PRODUCT_NAMES
from custom.intrahealth import PRODUCT_MAPPING
from custom.intrahealth.report_calcs import _locations_per_type
from custom.intrahealth.utils import YEKSI_NAA_REPORTS_VISITE_DE_L_OPERATOUR, \
    YEKSI_NAA_REPORTS_VISITE_DE_L_OPERATOUR_PER_PRODUCT, YEKSI_NAA_REPORTS_LOGISTICIEN, \
    YEKSI_NAA_REPORTS_VISITE_DE_L_OPERATOUR_PER_PROGRAM, \
    OPERATEUR_COMBINED, OPERATEUR_COMBINED2, COMMANDE_COMBINED, RAPTURE_COMBINED, LIVRAISON_COMBINED, \
    RECOUVREMENT_COMBINED, INDICATEURS_DE_BASE, YEKSI_NAA_REPORTS_CONSUMPTION
from dateutil.rrule import rrule, MONTHLY
from dateutil.relativedelta import relativedelta
from django.utils.functional import cached_property
from sqlagg.filters import EQ, BETWEEN, AND, GTE, LTE, NOT, IN, SqlFilter, OR
from corehq.apps.reports.sqlreport import DatabaseColumn, SqlData, AggregateColumn
from django.utils.translation import ugettext as _
from sqlalchemy import select
from corehq.apps.reports.util import get_INFilter_bindparams
from custom.utils.utils import clean_IN_filter_value
from memoized import memoized
from dimagi.utils.parsing import json_format_date
from functools import reduce

PRODUCT_NAMES = {
    'diu': ["diu"],
    'jadelle': ["jadelle"],
    'depo-provera': ["d\xe9po-provera", "depo-provera"],
    'd\xe9po-provera': ["d\xe9po-provera", "depo-provera"],
    'microlut/ovrette': ["microlut/ovrette"],
    'microgynon/lof.': ["microgynon/lof."],
    'preservatif masculin': ["pr\xe9servatif masculin", "preservatif masculin"],
    'preservatif feminin': ["pr\xe9servatif f\xe9minin", "preservatif feminin"],
    'cu': ["cu"],
    'collier': ["collier"]
}


def _locations_filter(archived_locations, location_field_name='location_id'):
    return NOT(IN(location_field_name, get_INFilter_bindparams('archived_locations', archived_locations)))


def normalize_decimal(element):
    if isinstance(element, Decimal):
        return round(float(element), 2) if element % 1 != 0 else int(element)
    else:
        return element


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
        rows = list(formatter.format(self.data, keys=self.keys, group_by=self.group_by))
        return rows

    # this is copy/paste from the
    # https://github.com/dimagi/commcare-hq/blob/master/corehq/apps/reports/sqlreport.py#L383
    # we added possibility to sum Float values
    def calculate_total_row(self, rows):
        total_row = []
        if len(rows) > 0:
            num_cols = len(rows[0])
            for i in range(num_cols):
                colrows = [cr[i] for cr in rows if isinstance(cr[i], dict)]
                columns = [r.get('sort_key') for r in colrows if
                           isinstance(r.get('sort_key'), (int, float))]
                if len(columns):
                    total_row.append(reduce(lambda x, y: x + y, columns, 0))
                else:
                    total_row.append('')
        return total_row

    @property
    def filter_values(self):
        return clean_IN_filter_value(super(BaseSqlData, self).filter_values, 'archived_locations')


class ConventureData(BaseSqlData):
    slug = 'conventure'
    title = 'Converture'
    show_total = False
    table_name = 'fluff_CouvertureFluff'
    custom_total_calculate = True

    @property
    def filters(self):
        # We have to filter data by real_date_repeat not date(first position in filters list).
        # Filtering is done directly in columns method(CountUniqueColumn).
        filters = super(ConventureData, self).filters
        filters.append(AND([GTE('real_date_repeat', "strsd"), LTE('real_date_repeat', "stred")]))
        if 'archived_locations' in self.config:
            filters.append(_locations_filter(self.config['archived_locations']))
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

        # Months are displayed in chronological order
        if 'month' in self.group_by:
            from custom.intrahealth.reports.utils import get_localized_months
            return sorted(rows, key=lambda row: get_localized_months().index(row[0]))

        return rows

    def calculate_total_row(self, rows):
        total_row = super(ConventureData, self).calculate_total_row(rows)
        if len(total_row) != 0:
            # two cell's are recalculated because the summation of percentage gives us bad values
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
        group_by.append('product_id')
        return group_by

    @property
    @memoized
    def products(self):
        return list(SQLProduct.objects.filter(domain=self.config['domain'], is_archived=False).order_by('name'))

    @property
    def rows(self):
        products = self.products
        values = {
            product.product_id: [0, 0, 0]
            for product in products
        }

        rows = self.get_data()
        for row in rows:
            product_id = row['product_id']
            values[product_id] = [
                row['commandes_total'],
                row['recus_total'],
                "%d%%" % (100 * row['recus_total']['html'] / (row['commandes_total']['html'] or 1))
            ]

        commandes = ['Commandes']
        raux = ['Raux']
        taux = ['Taux']

        for product in products:
            values_for_product = values[product.product_id]
            commandes.append(values_for_product[0])
            raux.append(values_for_product[1])
            taux.append(values_for_product[2])

        return [commandes, raux, taux]

    @property
    def headers(self):
        headers = DataTablesHeader(DataTablesColumn('Quantity'))
        for product in self.products:
            headers.add_column(DataTablesColumn(product.name))
        return headers

    @property
    def columns(self):
        return [
            DatabaseColumn('Product Name', SimpleColumn('product_id')),
            DatabaseColumn("Commandes", SumColumn('commandes_total')),
            DatabaseColumn("Recu", SumColumn('recus_total'))
        ]


class TauxDeRuptures(BaseSqlData):
    slug = 'taux_de_ruptures'
    title = 'Disponibilité des Produits - Taux des Ruptures de Stock'
    table_name = 'fluff_IntraHealthFluff'
    col_names = ['total_stock_total']
    have_groups = False
    custom_total_calculate = True

    @property
    def group_by(self):
        group_by = ['product_id']
        if 'region_id' in self.config:
            group_by.append('district_name')
        else:
            group_by.append('PPS_name')

        return group_by

    @property
    def filters(self):
        filter = super(TauxDeRuptures, self).filters
        filter.append(EQ("total_stock_total", "zero"))
        if 'archived_locations' in self.config:
            filter.append(_locations_filter(self.config['archived_locations']))
        return filter

    @property
    def columns(self):
        columns = []
        if 'region_id' in self.config:
            columns.append(DatabaseColumn(_("District"), SimpleColumn('district_name')))
        else:
            columns.append(DatabaseColumn(_("PPS"), SimpleColumn('PPS_name')))

        columns.append(DatabaseColumn(
            _("Stock total"),
            CountColumn('total_stock_total'),
            format_fn=lambda x: 1 if x > 0 else 0
        ))
        return columns

    def calculate_total_row(self, rows):
        conventure = ConventureData(self.config)
        if self.config['startdate'].month != self.config['enddate'].month:
            conventure_data_rows = conventure.calculate_total_row(conventure.rows)
            total = conventure_data_rows[3] if conventure_data_rows else 0
        else:
            conventure_data_rows = conventure.rows
            total = conventure_data_rows[0][2]["html"] if conventure_data_rows else 0

        def get_value(x):
            """x can be a value or a sort_key/html dict"""
            return x["sort_key"] if isinstance(x, dict) else x

        for row in rows:
            value = 1 if any(get_value(x) for x in row[1:]) else 0
            row.append({'sort_key': value, 'html': value})

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
            filters.append(_locations_filter(self.config['archived_locations']))
        return filters

    @property
    def group_by(self):
        return ['product_id', 'PPS_name']

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
            filters.append(_locations_filter(self.config['archived_locations']))
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

        columns.append(DatabaseColumn(_("PPS Avec Données Soumises"),
                                      CountUniqueAndSumCustomColumn('location_id'),
                                      format_fn=lambda x: {'sort_key': int(x), 'html': int(x)})
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
        return rows + [[location, {'sort_key': 0, 'html': 0}] for location in locations_not_included]


class DateSource(BaseSqlData):
    title = ''
    table_name = 'fluff_RecapPassageFluff'

    @property
    def filters(self):
        filters = super(DateSource, self).filters
        if 'location_id' in self.config:
            filters.append(EQ('location_id', 'location_id'))
        filters.append(NOT(EQ('product_id', 'empty_prd_code')))
        return filters

    @property
    def group_by(self):
        return ['date', ]

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
        filters.append(NOT(EQ('product_id', 'empty_prd_code')))
        return filters

    @property
    def group_by(self):
        return ['date', 'product_id']

    @property
    def columns(self):
        diff = lambda x, y: (x or 0) - (y or 0)

        def get_prd_name(id):
            try:
                return SQLProduct.objects.get(product_id=id, domain=self.config['domain'],
                                              is_archived=False).name
            except SQLProduct.DoesNotExist:
                pass

        return [
            DatabaseColumn(_("Designations"), SimpleColumn('product_id'),
                           format_fn=lambda id: get_prd_name(id)),
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
            filters.append(_locations_filter(self.config['archived_locations']))
        return filters

    @property
    def group_by(self):
        group_by = ['product_id']
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
            filters.append(_locations_filter(self.config['archived_locations']))
        return filters

    @property
    def group_by(self):
        group_by = []
        if 'region_id' in self.config:
            group_by.extend(['district_name', 'PPS_name'])
        else:
            group_by.append('PPS_name')
        group_by.append('product_id')
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
                                       [AliasColumn('stock'), AliasColumn('consumption')],
                                       slug='taux-consommation'))
        return columns

    def calculate_total_row(self, rows):
        total_row = []
        if len(rows) > 0:
            num_cols = len(rows[0])
            for i in range(num_cols):
                if i != 0 and i % 3 == 0:
                    cp = total_row[-2:]
                    total_row.append("%s%%" % (100 * int(cp[0] or 0) // (cp[1] or 1)))
                else:
                    colrows = [cr[i] for cr in rows if isinstance(cr[i], dict)]
                    columns = [
                        r.get('sort_key')
                        for r in colrows
                        if isinstance(r.get('sort_key'), int)
                    ]
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
            filters.append(_locations_filter(self.config['archived_locations']))
        return filters

    @property
    def group_by(self):
        group_by = []
        if 'region_id' in self.config:
            group_by.extend(['district_name', 'PPS_name'])
        else:
            group_by.append('PPS_name')
        group_by.append('product_id')

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
                    columns = [r.get('sort_key') for r in colrows if
                               isinstance(r.get('sort_key'), (float, int))]
                    if len(columns):
                        total_row.append(reduce(lambda x, y: x + y, columns, 0))
                    else:
                        total_row.append('')

        return total_row


class GestionDeLIPMTauxDeRuptures(TauxDeRuptures):
    table_name = 'fluff_TauxDeRuptureFluff'
    title = 'Gestion de l`IPM - Taux des Ruptures de Stock'

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
    title = 'Durée moyenne des retards de livraison'
    table_name = 'fluff_LivraisonFluff'
    have_groups = False
    col_names = ['duree_moyenne_livraison_total']

    @property
    def group_by(self):
        return ['district_name']

    @property
    def columns(self):
        columns = [DatabaseColumn(_("District"), SimpleColumn('district_name')),
                   DatabaseColumn(_("Retards de livraison (jours)"),
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
    title = 'Recouvrement des côuts - Taxu de Recouvrement'

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
        columns.append(DatabaseColumn(_("Montant dû"), SumColumn('payments_amount_to_pay')))
        columns.append(DatabaseColumn(_("Montant payé"), SumColumn('payments_amount_paid')))
        columns.append(DatabaseColumn(_("Payé dans le 30 jours"), SumColumn('payments_in_30_days')))
        columns.append(DatabaseColumn(_("Payé dans le 3 mois"), SumColumn('payments_in_3_months')))
        columns.append(DatabaseColumn(_("Payé dans l`annèe"), SumColumn('payments_in_year')))
        return columns

    def calculate_total_row(self, rows):
        total_row = super(RecouvrementDesCouts, self).calculate_total_row(rows)
        if total_row:
            total_row[0] = 'Total Region'
        return total_row


class IntraHealthQueryMeta(QueryMeta):

    def __init__(self, table_name, filters, group_by, distinct_on, key):
        self.key = key
        super(IntraHealthQueryMeta, self).__init__(table_name, filters, group_by, distinct_on, [])
        assert len(filters) > 0
        self.filter = AND(self.filters) if len(self.filters) > 1 else self.filters[0]

    def execute(self, connection, filter_values):
        return connection.execute(self._build_query(filter_values)).fetchall()

    def _build_query(self, filter_values):
        raise NotImplementedError()


class SumAndAvgQueryMeta(IntraHealthQueryMeta):

    def _build_query(self, filter_values):
        key_column = sqlalchemy.column(self.key)
        group_by_columns = [sqlalchemy.column(c) for c in self.group_by]
        sum_query = sqlalchemy.alias(
            sqlalchemy.select(
                group_by_columns + [sqlalchemy.func.sum(key_column).label('sum_col')] + [sqlalchemy.column('month')],
                group_by=self.group_by + [sqlalchemy.column('month')],
                whereclause=self.filter.build_expression(),
            ).select_from(sqlalchemy.table(self.table_name)),
            name='s')

        return select(
            group_by_columns + [sqlalchemy.func.avg(sum_query.c.sum_col).label(self.key)],
            group_by=self.group_by,
            from_obj=sum_query
        ).params(filter_values)


class CountUniqueAndSumQueryMeta(IntraHealthQueryMeta):

    def _build_query(self, filter_values):
        key_column = sqlalchemy.column(self.key)
        group_by_columns = [sqlalchemy.column(c) for c in self.group_by]
        subquery = sqlalchemy.alias(
            sqlalchemy.select(
                group_by_columns + [sqlalchemy.func.count(sqlalchemy.distinct(key_column)).label('count_unique')],
                group_by=self.group_by + [sqlalchemy.column('month')],
                whereclause=self.filter.build_expression(),
            ).select_from(sqlalchemy.table(self.table_name)),
            name='cq')

        return sqlalchemy.select(
            group_by_columns + [sqlalchemy.func.sum(subquery.c.count_unique).label(self.key)],
            group_by=self.group_by,
            from_obj=subquery
        ).params(filter_values)


class IntraHealthCustomColumn(CustomQueryColumn):

    def get_query_meta(self, default_table_name, default_filters, default_group_by, default_distinct_on,
                       default_order_by):
        table_name = self.table_name or default_table_name
        filters = self.filters or default_filters
        group_by = self.group_by or default_group_by
        distinct_on = self.distinct_on or default_distinct_on
        return self.query_cls(table_name, filters, group_by, distinct_on, self.key)


class SumAndAvgGCustomColumn(IntraHealthCustomColumn):
    query_cls = SumAndAvgQueryMeta
    name = 'sum_and_avg'


class CountUniqueAndSumCustomColumn(IntraHealthCustomColumn):
    query_cls = CountUniqueAndSumQueryMeta
    name = 'count_unique_and_sum'


class IntraHealthSqlData(SqlData):
    datatables = False
    show_charts = False
    show_total = False
    custom_total_calculate = False
    no_value = {'sort_key': 0, 'html': 0}
    fix_left_col = False

    def percent_fn(self, x, y):
        return "%(p).2f%%" % \
               {
                   "p": (100 * float(y or 0) / float(x or 1))
               }

    def format_data_and_cast_to_float(self, value):
        return {"html": "{:.2f}".format(value), "sort_key": "{:.2f}".format(value)} if value is not None else value

    @property
    def engine_id(self):
        return 'ucr'

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
        rows = list(formatter.format(self.data, keys=self.keys, group_by=self.group_by))
        return rows

    @property
    def filter_values(self):
        return clean_IN_filter_value(super(IntraHealthSqlData, self).filter_values, 'archived_locations')


class RecouvrementDesCouts2(IntraHealthSqlData):
    show_total = True
    slug = 'recouvrement'
    title = 'Recouvrement des côuts - Taxu de Recouvrement'

    @property
    def table_name(self):
        return get_table_name(self.config['domain'], RECOUVREMENT_COMBINED)

    @property
    def filters(self):
        filters = [BETWEEN("date_du", "startdate", "enddate")]
        if 'region_id' in self.config:
            filters.append(EQ("region_id", "region_id"))
        elif 'district_id' in self.config:
            filters.append(EQ("district_id", "district_id"))
        return filters

    @property
    def group_by(self):
        return ['district_name']

    @property
    def columns(self):
        columns = [DatabaseColumn(_("District"), SimpleColumn('district_name'))]
        columns.append(DatabaseColumn(_("Montant dû"), SumColumn('quantite_reale_a_payer')))
        columns.append(DatabaseColumn(_("Montant payé"), SumColumn('montant_paye')))
        columns.append(DatabaseColumn(_("Payé dans le 30 jours"), SumColumn('payee_trent_jour')))
        columns.append(DatabaseColumn(_("Payé dans le 3 mois"), SumColumn('payee_trois_mois')))
        columns.append(DatabaseColumn(_("Payé dans l`annèe"), SumColumn('payee_un_an')))
        return columns

    def get_value(self, cell):
        if cell:
            return cell['html']
        return 0

    @property
    def rows(self):
        loc_names = set()
        rows = self.get_data()
        loc_name = 'district_name'

        data = {}
        for row in rows:
            if row.get(loc_name):
                loc_names.add(row[loc_name])
                if row[loc_name] not in data:
                    data[row[loc_name]] = defaultdict(int)
                data[row[loc_name]]['quantite_reale_a_payer'] += self.get_value(row['quantite_reale_a_payer'])
                data[row[loc_name]]['montant_paye'] += self.get_value(row['montant_paye'])
                data[row[loc_name]]['payee_trent_jour'] += self.get_value(row['payee_trent_jour'])
                data[row[loc_name]]['payee_trois_mois'] += self.get_value(row['payee_trois_mois'])
                data[row[loc_name]]['payee_un_an'] += self.get_value(row['payee_un_an'])

        loc_names = sorted(loc_names)

        rows = []
        total_values = {
            'quantite_reale_a_payer': 0,
            'montant_paye': 0,
            'payee_trent_jour': 0,
            'payee_trois_mois': 0,
            'payee_un_an': 0,
        }
        for loc_name in loc_names:
            rows.append([
                loc_name,
                data[loc_name]['quantite_reale_a_payer'],
                data[loc_name]['montant_paye'],
                data[loc_name]['payee_trent_jour'],
                data[loc_name]['payee_trois_mois'],
                data[loc_name]['payee_un_an'],
            ])
            total_values['quantite_reale_a_payer'] += data[loc_name]['quantite_reale_a_payer']
            total_values['montant_paye'] += data[loc_name]['montant_paye']
            total_values['payee_trent_jour'] += data[loc_name]['payee_trent_jour']
            total_values['payee_trois_mois'] += data[loc_name]['payee_trois_mois']
            total_values['payee_un_an'] += data[loc_name]['payee_un_an']

        total_row = [
            'Total Region',
            total_values['quantite_reale_a_payer'],
            total_values['montant_paye'],
            total_values['payee_trent_jour'],
            total_values['payee_trois_mois'],
            total_values['payee_un_an'],
        ]
        self.total_row = total_row
        return rows

    @property
    def headers(self):
        return DataTablesHeader(
            DataTablesColumn('District'),
            DataTablesColumn('Montant dû'),
            DataTablesColumn('Montant payé'),
            DataTablesColumn('Payé dans le 30 jours'),
            DataTablesColumn('Payé dans le 3 mois'),
            DataTablesColumn('Payé dans l`annèe'),
        )


class DureeData2(IntraHealthSqlData):
    show_total = True
    slug = 'duree'
    title = 'Durée moyenne des retards de livraison'

    @property
    def table_name(self):
        return get_table_name(self.config['domain'], LIVRAISON_COMBINED)

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
        return ['district_name', 'date']

    @property
    def columns(self):
        columns = [
            DatabaseColumn(_("District"), SimpleColumn('district_name')),
            DatabaseColumn(_("date"), MonthColumn('date')),
            DatabaseColumn(_("Retards de livraison (jours)"), SumColumn('duree_moyenne_livraison')),
        ]
        return columns

    def get_value(self, cell):
        if cell:
            return cell['html']
        return 0

    @property
    def rows(self):
        loc_names = set()
        rows = self.get_data()
        loc_name = 'district_name'

        data = defaultdict(list)
        for row in rows:
            if row.get(loc_name):
                loc_names.add(row[loc_name])
                data[row[loc_name]].append(self.get_value(row['duree_moyenne_livraison']))

        loc_names = sorted(loc_names)

        rows = []
        total_sum = 0
        total_len = 0
        for loc_name in loc_names:
            rows.append([
                loc_name,
                "{:.2f}".format(sum(data[loc_name]) / (len(data[loc_name]) or 1))
            ])
            total_sum += sum(data[loc_name])
            total_len += len(data[loc_name])

        total_row = [
            'Moyenne Region',
            "{:.2f}".format(total_sum / (total_len or 1))
        ]
        self.total_row = total_row
        return rows

    @property
    def headers(self):
        return DataTablesHeader(
            DataTablesColumn('District'),
            DataTablesColumn('Retards de livraison (jours)'),
        )


class GestionDeLIPMTauxDeRuptures2(IntraHealthSqlData):
    show_total = True
    title = 'Gestion de l`IPM - Taux des Ruptures de Stock'
    product_names = {
        "collier": None,
        "depoprovera": None,
        "diu": None,
        "jadelle": None,
        "microgynon": None,
        "microlut": None,
        "cu": None,
        "preservatif_feminin": None,
        "preservatif_masculin": None,
        "sayana_press": None,
        "implanon": None,
    }

    @property
    def table_name(self):
        return get_table_name(self.config['domain'], RAPTURE_COMBINED)

    @property
    def filters(self):
        filters = [BETWEEN("date_rapportage", "startdate", "enddate")]
        if 'region_id' in self.config:
            filters.append(EQ("region_id", "region_id"))
        elif 'district_id' in self.config:
            filters.append(EQ("district_id", "district_id"))
        return filters

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
        columns = [
            DatabaseColumn(_("collier"), SumColumn('rupture_collier_hv')),
            DatabaseColumn(_("depoprovera"), SumColumn('rupture_depoprovera_hv')),
            DatabaseColumn(_("diu"), SumColumn('rupture_diu_hv')),
            DatabaseColumn(_("jadelle"), SumColumn('rupture_jadelle_hv')),
            DatabaseColumn(_("microgynon"), SumColumn('rupture_microgynon_hv')),
            DatabaseColumn(_("microlut"), SumColumn('rupture_microlut_hv')),
            DatabaseColumn(_("cu"), SumColumn('rupture_cu_hv')),
            DatabaseColumn(_("preservatif_feminin"), SumColumn('rupture_preservatif_feminin_hv')),
            DatabaseColumn(_("preservatif_masculin"), SumColumn('rupture_preservatif_masculin_hv')),
            DatabaseColumn(_("sayana_press"), SumColumn('rupture_sayana_press_hv')),
            DatabaseColumn(_("implanon"), SumColumn('rupture_implanon_hv')),
        ]
        if 'region_id' in self.config:
            columns.append(DatabaseColumn(_("District"), SimpleColumn('district_name')))
        else:
            columns.append(DatabaseColumn(_("PPS"), SimpleColumn('pps_name')))
        return columns

    def get_value(self, cell):
        if cell:
            return cell['html']
        return 0

    @property
    def rows(self):
        loc_names = set()
        rows = self.get_data()
        if 'region_id' in self.config:
            loc_name = 'district_name'
        else:
            loc_name = 'pps_name'

        data = {}
        product_data = defaultdict(int)
        for row in rows:
            if row.get(loc_name):
                loc_names.add(row[loc_name])
                if row[loc_name] not in data:
                    data[row[loc_name]] = defaultdict(int)
                for raw_product_name in self.product_names:
                    if self.product_names[raw_product_name] is None:
                        product_name = INIT_PRODUCT_NAMES.get(PRODUCT_MAPPING[raw_product_name].lower())
                        if product_name is not None:
                            try:
                                product = SQLProduct.active_objects.get(name__iexact=product_name,
                                                                        domain=self.config['domain'])
                                self.product_names[raw_product_name] = product.name
                            except SQLProduct.DoesNotExist:
                                self.product_names[raw_product_name] = ''
                    product_field = self.get_value(row['rupture_{}_hv'.format(raw_product_name)])
                    data[row[loc_name]][raw_product_name] += product_field
                    product_data[raw_product_name] += product_field

        raw_product_names = sorted(
            product_name for product_name in self.product_names if self.product_names[product_name]
        )

        rows = []
        loc_names = sorted(loc_names)
        for loc_name in loc_names:
            values = data[loc_name]
            row = [loc_name]
            for raw_product_name in raw_product_names:
                row.append(values[raw_product_name])
            rows.append(row)
        total_row = ['Taux rupture']
        number_of_locs = len(data) or 1
        for raw_product_name in raw_product_names:
            total_row.append('({0}/{1}) {2:.2f}%'.format(
                product_data[raw_product_name], number_of_locs,
                (product_data[raw_product_name] * 100) / number_of_locs,
            ))
        self.total_row = total_row
        return rows

    @property
    def headers(self):
        if 'region_id' in self.config:
            headers = DataTablesHeader(
                DataTablesColumn('District'),
            )
        else:
            headers = DataTablesHeader(
                DataTablesColumn('PPS'),
            )
        raw_product_names = sorted(
            product_name for product_name in self.product_names if self.product_names[product_name]
        )
        for raw_product_name in raw_product_names:
            headers.add_column(
                DataTablesColumn(self.product_names[raw_product_name])
            )
        return headers


class NombreData2(IntraHealthSqlData):
    show_total = True
    slug = 'nombre'
    title = 'Nombre de mois de stock disponibles et utilisables aux PPS'
    product_names = set()

    @property
    def table_name(self):
        return get_table_name(self.config['domain'], OPERATEUR_COMBINED)

    @property
    def filters(self):
        filters = [BETWEEN("real_date", "startdate", "enddate")]
        loc_name = None
        if 'region_id' in self.config:
            loc_name = 'region_id'
        elif 'district_id' in self.config:
            loc_name = 'district_id'
        if loc_name:
            filters.append(EQ(loc_name, loc_name))
            if 'archived_locations' in self.config:
                filters.append(_locations_filter(self.config['archived_locations'], loc_name))
        return filters

    @property
    def group_by(self):
        group_by = ['doc_id', 'product_name', 'display_total_stock', 'default_consumption']
        if 'region_id' in self.config:
            group_by.append('district_name')
        else:
            group_by.append('pps_name')
        return group_by

    @property
    def columns(self):
        columns = [
            DatabaseColumn(_("Product Name"), SimpleColumn('product_name')),
            DatabaseColumn(_("Display Total Stock"), SimpleColumn('display_total_stock')),
            DatabaseColumn(_("Default Consumption"), SimpleColumn('default_consumption')),
        ]
        if 'region_id' in self.config:
            columns.append(DatabaseColumn(_("District"), SimpleColumn('district_name')))
        else:
            columns.append(DatabaseColumn(_("PPS"), SimpleColumn('pps_name')))
        return columns

    @property
    def rows(self):
        product_names = set()
        loc_names = set()
        rows = self.get_data()

        if 'region_id' in self.config:
            loc_name = 'district_name'
        else:
            loc_name = 'pps_name'

        data = {}
        for row in rows:
            if row.get('product_name') and row.get(loc_name):
                loc_names.add(row[loc_name])
                product_names.add(row['product_name'])
                if row[loc_name] not in data:
                    data[row[loc_name]] = {}
                if row['product_name'] not in data[row[loc_name]]:
                    data[row[loc_name]][row['product_name']] = defaultdict(list)
                data[row[loc_name]][row['product_name']]['display_total_stock'].append(row['display_total_stock'])
                data[row[loc_name]][row['product_name']]['default_consumption'].append(row['default_consumption'])

        loc_names = sorted(loc_names)
        product_names = sorted(product_names)
        self.product_names = product_names
        rows = []
        display_total_stock_per_product = defaultdict(int)
        default_consumption_per_product = defaultdict(int)
        for loc_name in loc_names:
            row = [loc_name]
            for product_name in product_names:
                display_total_stock = 0
                default_consumption = 0
                if data.get(loc_name) and data[loc_name].get(product_name):
                    display_total_stock = [
                        value for value in data[loc_name][product_name]['display_total_stock'] if value is not None
                    ]
                    default_consumption = [
                        value for value in data[loc_name][product_name]['default_consumption'] if value is not None
                    ]
                if display_total_stock:
                    display_total_stock = sum(display_total_stock) / len(display_total_stock)
                if default_consumption:
                    default_consumption = sum(default_consumption) / len(default_consumption)
                row.append(self.format_data_and_cast_to_float(display_total_stock))
                display_total_stock_per_product[product_name] += display_total_stock
                row.append(self.format_data_and_cast_to_float(default_consumption))
                default_consumption_per_product[product_name] += default_consumption
                row.append("{:0.3f}".format(
                    float(display_total_stock) /
                    (float(default_consumption) or 1.0)
                ))
            rows.append(row)
        total_row = ['']
        for product_name in product_names:
            total_row.append(display_total_stock_per_product[product_name])
            total_row.append(default_consumption_per_product[product_name])
            total_row.append("{:0.3f}".format(
                float(display_total_stock_per_product[product_name]) /
                (float(default_consumption_per_product[product_name]) or 1.0)
            ))
        self.total_row = total_row
        return rows

    @property
    def headers(self):
        headers = DataTablesHeader()
        if 'region_id' in self.config:
            headers.add_column(DataTablesColumnGroup('', DataTablesColumn('District')))
        else:
            headers.add_column(DataTablesColumnGroup('', DataTablesColumn('PPS')))

        for product_name in self.product_names:
            headers.add_column(DataTablesColumnGroup(
                product_name,
                DataTablesColumn('Quantite produits entreposes au PPS'),
                DataTablesColumn('CMM'),
                DataTablesColumn('Nombre mois stock disponible et utilisable')
            ))

        return headers


class TauxConsommationData2(IntraHealthSqlData):
    show_total = True
    slug = 'taux_consommation'
    title = 'Taux de Consommation'
    product_names = set()

    @property
    def table_name(self):
        return get_table_name(self.config['domain'], OPERATEUR_COMBINED)

    @property
    def filters(self):
        filters = [BETWEEN("real_date", "startdate", "enddate")]
        loc_name = None
        if 'region_id' in self.config:
            loc_name = 'region_id'
        elif 'district_id' in self.config:
            loc_name = 'district_id'
        if loc_name:
            filters.append(EQ(loc_name, loc_name))
            if 'archived_locations' in self.config:
                filters.append(_locations_filter(self.config['archived_locations'], loc_name))
        return filters

    @property
    def group_by(self):
        group_by = ['doc_id', 'product_name', 'actual_consumption', 'total_stock']
        if 'region_id' in self.config:
            group_by.append('district_name')
        else:
            group_by.append('pps_name')
        return group_by

    @property
    def columns(self):
        columns = [
            DatabaseColumn(_("Product Name"), SimpleColumn('product_name')),
            DatabaseColumn(_("Consommation reelle"), SimpleColumn('actual_consumption')),
            DatabaseColumn(_("Stock apres derniere livraison"), SimpleColumn('total_stock')),
        ]
        if 'region_id' in self.config:
            columns.append(DatabaseColumn(_("District"), SimpleColumn('district_name')))
        else:
            columns.append(DatabaseColumn(_("PPS"), SimpleColumn('pps_name')))
        return columns

    @property
    def rows(self):
        product_names = set()
        loc_names = set()
        rows = self.get_data()

        if 'region_id' in self.config:
            loc_name = 'district_name'
        else:
            loc_name = 'pps_name'

        data = {}
        for row in rows:
            if row.get('product_name') and row.get(loc_name):
                loc_names.add(row[loc_name])
                product_names.add(row['product_name'])
                if row[loc_name] not in data:
                    data[row[loc_name]] = {}
                if row['product_name'] not in data[row[loc_name]]:
                    data[row[loc_name]][row['product_name']] = defaultdict(list)
                data[row[loc_name]][row['product_name']]['actual_consumption'].append(row['actual_consumption'])
                data[row[loc_name]][row['product_name']]['total_stock'].append(row['total_stock'])

        loc_names = sorted(loc_names)
        product_names = sorted(product_names)
        self.product_names = product_names
        rows = []
        actual_consumption_per_product = defaultdict(int)
        total_stock_per_product = defaultdict(int)
        for loc_name in loc_names:
            row = [loc_name]
            for product_name in product_names:
                actual_consumption = 0
                total_stock = 0
                if data.get(loc_name) and data[loc_name].get(product_name):
                    actual_consumption = [
                        value for value in data[loc_name][product_name]['actual_consumption'] if value is not None
                    ]
                    total_stock = [
                        value for value in data[loc_name][product_name]['total_stock'] if value is not None
                    ]
                if actual_consumption:
                    actual_consumption = sum(actual_consumption) / len(actual_consumption)
                if total_stock:
                    total_stock = sum(total_stock) / len(total_stock)
                row.append(self.format_data_and_cast_to_float(actual_consumption))
                actual_consumption_per_product[product_name] += actual_consumption
                row.append(self.format_data_and_cast_to_float(total_stock))
                total_stock_per_product[product_name] += total_stock
                row.append(self.percent_fn(total_stock, actual_consumption))
            rows.append(row)
        total_row = ['']
        for product_name in product_names:
            total_row.append(actual_consumption_per_product[product_name])
            total_row.append(total_stock_per_product[product_name])
            total_row.append(self.percent_fn(
                total_stock_per_product[product_name],
                actual_consumption_per_product[product_name],
            ))
        self.total_row = total_row
        return rows

    @property
    def headers(self):
        headers = DataTablesHeader()
        if 'region_id' in self.config:
            headers.add_column(DataTablesColumnGroup('', DataTablesColumn('District')))
        else:
            headers.add_column(DataTablesColumnGroup('', DataTablesColumn('PPS')))

        for product_name in self.product_names:
            headers.add_column(DataTablesColumnGroup(
                product_name,
                DataTablesColumn('Consommation reelle'),
                DataTablesColumn('Stock apres derniere livraison'),
                DataTablesColumn('Taux consommation')
            ))

        return headers


class TauxDeRuptures2(IntraHealthSqlData):
    show_total = True
    slug = 'taux_de_ruptures2'
    title = 'Disponibilité des Produits - Taux des Ruptures de Stock'
    product_names = set()

    @property
    def group_by(self):
        group_by = ['product_name']
        if 'region_id' in self.config:
            group_by.append('district_name')
        else:
            group_by.append('pps_name')
        return group_by

    @property
    def filters(self):
        filters = [BETWEEN("real_date", "startdate", "enddate")]
        loc_name = None
        if 'region_id' in self.config:
            loc_name = 'region_id'
        elif 'district_id' in self.config:
            loc_name = 'district_id'
        if loc_name:
            filters.append(EQ(loc_name, loc_name))
            if 'archived_locations' in self.config:
                filters.append(_locations_filter(self.config['archived_locations'], loc_name))
        return filters

    @property
    def columns(self):
        columns = [
            DatabaseColumn(_("Product Name"), SimpleColumn('product_name')),
        ]
        if 'region_id' in self.config:
            columns.append(DatabaseColumn(_("District"), SimpleColumn('district_name')))
        else:
            columns.append(DatabaseColumn(_("PPS"), SimpleColumn('pps_name')))

        columns.append(DatabaseColumn(
            _("Stock total"), CountColumn('total_stock'), format_fn=lambda x: 1 if x > 0 else 0
        ))
        return columns

    @property
    def table_name(self):
        return get_table_name(self.config['domain'], OPERATEUR_COMBINED)

    @property
    def rows(self):
        loc_names = set()
        product_names = set()
        rows = self.get_data()

        if 'region_id' in self.config:
            loc_name = 'district_name'
        else:
            loc_name = 'pps_name'

        data = {}
        product_data = defaultdict(int)
        for row in rows:
            if row.get('product_name'):
                loc_names.add(row[loc_name])
                product_names.add(row['product_name'])
                if row[loc_name] not in data:
                    data[row[loc_name]] = defaultdict(int)
                data[row[loc_name]][row['product_name']] += row['total_stock']
                product_data[row['product_name']] += row['total_stock']

        product_names = sorted(product_names)
        self.product_names = product_names
        rows = []

        loc_names = sorted(loc_names)

        for loc_name in loc_names:
            values = data[loc_name]
            row = [loc_name]
            for product_name in product_names:
                row.append(values[product_name])
            rows.append(row)
        row = ['Total']
        total_row = ['Taux rupture']
        number_of_locs = len(data) or 1
        for product_name in product_names:
            row.append(product_data[product_name])
            total_row.append('({0}/{1}) {2:.2f}%'.format(
                product_data[product_name], number_of_locs, (product_data[product_name] * 100) / number_of_locs,
            ))
        rows.append(row)
        self.total_row = total_row

        return rows

    @property
    def headers(self):
        headers = DataTablesHeader()
        if 'region_id' in self.config:
            headers.add_column(
                DataTablesColumn('District')
            )
        else:
            headers.add_column(
                DataTablesColumn('PPS')
            )
        for product_name in self.product_names:
            headers.add_column(
                DataTablesColumn(product_name)
            )
        return headers


class DateSource2(IntraHealthSqlData):
    slug = 'dateSource2'
    title = 'DateSource2'
    show_total = False

    @property
    def filters(self):
        filters = [BETWEEN("real_date", "startdate", "enddate")]
        if 'region_id' in self.config:
            filters.append(EQ("region_id", "region_id"))
        elif 'district_id' in self.config:
            filters.append(EQ("district_id", "district_id"))
        if 'location_id' in self.config:
            filters.append(EQ("location_id", "location_id"))
        return filters

    @property
    def group_by(self):
        return ['real_date', ]

    @property
    def columns(self):
        return [
            DatabaseColumn(_("Date"), SimpleColumn('real_date')),
        ]

    @property
    def table_name(self):
        return get_table_name(self.config['domain'], OPERATEUR_COMBINED)

    @property
    def total_row(self):
        return []

    @property
    def rows(self):
        rows = self.get_data()
        return sorted(list(
            set(row['real_date'] for row in rows)
        ))

    @property
    def headers(self):
        return []


class RecapPassageData2(IntraHealthSqlData):
    show_total = False

    @property
    def filters(self):
        filters = [BETWEEN("real_date", "startdate", "enddate")]
        if 'region_id' in self.config:
            filters.append(EQ("region_id", "region_id"))
        elif 'district_id' in self.config:
            filters.append(EQ("district_id", "district_id"))
        return filters

    @property
    def group_by(self):
        return ['real_date', 'product_name']

    @property
    def columns(self):
        return [
            DatabaseColumn(_("Designations"), SimpleColumn('product_name')),
            DatabaseColumn(_("Stock apres derniere livraison"), SumColumn('old_stock_total')),
            DatabaseColumn(_("Stock disponible et utilisable a la livraison"), SumColumn('total_stock')),
            DatabaseColumn(_("Stock Total"), SumColumn('display_total_stock', alias='stock_total')),
            DatabaseColumn(_("Precedent"), SumColumn('old_stock_pps')),
            DatabaseColumn(_("Recu hors entrepots mobiles"), SumColumn('outside_receipts_amt')),
            DatabaseColumn(_("Facturable"), SumColumn('billed_consumption')),
            DatabaseColumn(_("Reelle"), SumColumn('actual_consumption')),
            DatabaseColumn("Stock Total", AliasColumn('stock_total')),
            DatabaseColumn("PPS Restant", SumColumn('pps_stock')),
            DatabaseColumn("Pertes et Adjustement", SumColumn('loss_amt')),
            DatabaseColumn(_("Livraison"), SumColumn('livraison'))
        ]

    @property
    def table_name(self):
        return get_table_name(self.config['domain'], OPERATEUR_COMBINED)

    @property
    def slug(self):
        return 'recap_passage_%s' % json_format_date(self.config['startdate'])

    @property
    def title(self):
        return 'Recap Passage %s' % json_format_date(self.config['startdate'])

    @property
    def total_row(self):
        return []

    def get_value(self, cell):
        if cell:
            return cell['html']
        return 0

    @property
    def rows(self):
        rows = self.get_data()
        product_names = set()
        data = {}
        for row in rows:
            product_name = row['product_name']
            product_names.add(product_name)
            if not data.get(product_name):
                data[product_name] = defaultdict(int)
            product_data = data[product_name]
            product_data['old_stock_total'] += self.get_value(row['old_stock_total'])
            product_data['total_stock'] += self.get_value(row['total_stock'])
            product_data['livraison'] += self.get_value(row['livraison'])
            product_data['stock_total'] += self.get_value(row['stock_total'])
            product_data['old_stock_pps'] += self.get_value(row['old_stock_pps'])
            product_data['outside_receipts_amt'] += self.get_value(row['outside_receipts_amt'])
            product_data['billed_consumption'] += self.get_value(row['billed_consumption'])
            product_data['actual_consumption'] += self.get_value(row['actual_consumption'])
            product_data['pps_stock'] += self.get_value(row['pps_stock'])
            product_data['loss_amt'] += self.get_value(row['loss_amt'])

        rows = []
        product_names = sorted(product_names)
        for product_name in product_names:
            product_data = data[product_name]
            rows.append([
                product_name,
                product_data['old_stock_total'],
                product_data['total_stock'],
                product_data['livraison'],
                product_data['stock_total'],
                product_data['old_stock_pps'],
                product_data['outside_receipts_amt'],
                (product_data['actual_consumption'] or 0) - (product_data['billed_consumption'] or 0),
                product_data['billed_consumption'],
                product_data['actual_consumption'],
                product_data['stock_total'],
                product_data['pps_stock'],
                product_data['loss_amt'],
            ])
        return rows

    @property
    def headers(self):
        return DataTablesHeader(
            DataTablesColumn('Designations'),
            DataTablesColumn('Stock apres derniere livraison'),
            DataTablesColumn('Stock disponible et utilisable a la livraison'),
            DataTablesColumn('Livraison'),
            DataTablesColumn('Stock Total'),
            DataTablesColumn('Precedent'),
            DataTablesColumn('Recu hors entrepots mobiles'),
            DataTablesColumn('Non Facturable'),
            DataTablesColumn('Facturable'),
            DataTablesColumn('Reelle'),
            DataTablesColumn('Stock Total'),
            DataTablesColumn('PPS Restant'),
            DataTablesColumn('Pertes et Adjustement'),
        )


class ConsommationData2(IntraHealthSqlData):
    slug = 'consommation2'
    title = 'Consommation'
    show_total = True
    product_names = set()

    @property
    def table_name(self):
        return get_table_name(self.config['domain'], OPERATEUR_COMBINED)

    @property
    def filters(self):
        filters = [BETWEEN("real_date", "startdate", "enddate")]
        loc_name = None
        if 'region_id' in self.config:
            loc_name = 'region_id'
        elif 'district_id' in self.config:
            loc_name = 'district_id'
        if loc_name:
            filters.append(EQ(loc_name, loc_name))
            if 'archived_locations' in self.config:
                filters.append(_locations_filter(self.config['archived_locations'], loc_name))
        return filters

    @property
    def group_by(self):
        group_by = ['product_name']
        if 'region_id' in self.config:
            group_by.append('district_name')
        else:
            group_by.append('pps_name')

        return group_by

    @property
    def columns(self):
        columns = [
            DatabaseColumn(_("Product Name"), SimpleColumn('product_name')),
        ]
        if 'region_id' in self.config:
            columns.append(DatabaseColumn(_("District"), SimpleColumn('district_name')))
        else:
            columns.append(DatabaseColumn(_("PPS"), SimpleColumn('pps_name')))

        columns.append(DatabaseColumn(_("Consumption"), SumColumn('actual_consumption')))
        return columns

    def get_value(self, cell):
        if cell:
            return cell['html']
        return 0

    @property
    def rows(self):
        product_names = set()
        loc_names = set()
        rows = self.get_data()
        if 'region_id' in self.config:
            loc_name = 'district_name'
        else:
            loc_name = 'pps_name'

        data = {}
        product_data = defaultdict(int)
        for row in rows:
            if row.get('product_name'):
                product_names.add(row['product_name'])
                loc_names.add(row[loc_name])
                if row[loc_name] not in data:
                    data[row[loc_name]] = defaultdict(int)
                data[row[loc_name]][row['product_name']] += self.get_value(row['actual_consumption'])
                product_data[row['product_name']] += self.get_value(row['actual_consumption'])

        product_names = sorted(product_names)
        self.product_names = product_names
        loc_names = sorted(loc_names)
        rows = []
        for loc_name in loc_names:
            values = data[loc_name]
            row = [loc_name]
            for product_name in product_names:
                row.append(values[product_name])
            rows.append(row)
        total_row = ['Total']
        for product_name in product_names:
            total_row.append(product_data[product_name])
        self.total_row = total_row
        return rows

    @property
    def headers(self):
        if 'region_id' in self.config:
            headers = DataTablesHeader(
                DataTablesColumn('District'),
            )
        else:
            headers = DataTablesHeader(
                DataTablesColumn('PPS'),
            )
        for product_name in self.product_names:
            headers.add_column(
                DataTablesColumn(product_name)
            )
        return headers


class PPSAvecDonnees2(IntraHealthSqlData):
    slug = 'pps_avec_donnees2'
    title = 'PPS Avec Données'
    show_total = True

    @property
    def table_name(self):
        return get_table_name(self.config['domain'], OPERATEUR_COMBINED)

    @property
    def filters(self):
        filters = [BETWEEN("real_date_repeat", "startdate", "enddate")]
        loc_name = None
        if 'region_id' in self.config:
            loc_name = 'region_id'
        elif 'district_id' in self.config:
            loc_name = 'district_id'
        if loc_name:
            filters.append(EQ(loc_name, loc_name))
            if 'archived_locations' in self.config:
                filters.append(_locations_filter(self.config['archived_locations'], loc_name))
        return filters

    @property
    def group_by(self):
        group_by = ['pps_id']
        if 'region_id' in self.config:
            group_by.append('district_name')
        else:
            group_by.append('pps_name')
        return group_by

    @property
    def columns(self):
        columns = [DatabaseColumn(_("PPS ID"), SimpleColumn('pps_id'))]
        if 'region_id' in self.config:
            columns.append(DatabaseColumn(_("District"), SimpleColumn('district_name')))
        else:
            columns.append(DatabaseColumn(_("PPS"), SimpleColumn('pps_name')))
        return columns

    @property
    def rows(self):
        loc_names = set()
        values = {}
        if 'region_id' in self.config:
            loc_name = 'district_name'
        else:
            loc_name = 'pps_name'
        rows = self.get_data()
        for row in rows:
            if row.get(loc_name):
                loc_names.add(row[loc_name])
                if row[loc_name] not in values:
                    values[row[loc_name]] = set()
                values[row[loc_name]].add(row['pps_id'])

        rows = []
        loc_names = sorted(loc_names)
        for loc_name in loc_names:
            pps_ids = values[loc_name]
            rows.append([loc_name, len(pps_ids)])
        self.total_row = ['Total', sum(len(pps_ids) for pps_ids in values.values())]
        if 'district_id' in self.config:
            locations_included = [loc_name for loc_name in values]
        else:
            return rows

        all_locations = SQLLocation.objects.get(
            location_id=self.config['district_id']
        ).get_children().exclude(is_archived=True).values_list('name', flat=True)
        locations_not_included = set(all_locations) - set(locations_included)
        return rows + [[location, {'sort_key': 0, 'html': 0}] for location in locations_not_included]

    @property
    def headers(self):
        if 'district_id' in self.config:
            headers = DataTablesHeader(
                DataTablesColumn('District'),
            )
        else:
            headers = DataTablesHeader(
                DataTablesColumn('PPS'),
            )
        headers.add_column(DataTablesColumn('PPS Avec Données Soumises'))
        return headers


class ConventureData2(IntraHealthSqlData):
    slug = 'conventure2'
    title = 'Converture'
    show_total = True

    @property
    def table_name(self):
        return get_table_name(self.config['domain'], OPERATEUR_COMBINED)

    @property
    def filters(self):
        filters = [BETWEEN("real_date", "startdate", "enddate")]
        loc_name = None
        if 'region_id' in self.config:
            loc_name = 'region_id'
        elif 'district_id' in self.config:
            loc_name = 'district_id'
        if loc_name:
            filters.append(EQ(loc_name, loc_name))
            if 'archived_locations' in self.config:
                filters.append(_locations_filter(self.config['archived_locations'], loc_name))
        return filters

    @property
    def group_by(self):
        group_by = ['pps_id', 'real_date']
        if 'district_id' in self.config:
            group_by.append('district_id')
        else:
            group_by.append('region_id')
        return group_by

    @property
    def columns(self):
        columns = [
            DatabaseColumn('Mois', MonthColumn('real_date')),
            DatabaseColumn('pps_id', SimpleColumn('pps_id')),
        ]
        if 'district_id' in self.config:
            columns.append(DatabaseColumn('district_id', SimpleColumn('district_id')))
        else:
            columns.append(DatabaseColumn('region_id', SimpleColumn('region_id')))
        return columns

    @property
    def rows(self):
        values = {}
        if 'district_id' in self.config:
            loc_name = 'district_id'
        else:
            loc_name = 'region_id'

        registered = 0
        rows = self.get_data()
        for row in rows:
            month = int(row['real_date']['html'])
            if month not in values:
                values[month] = {
                    'pps_ids': set(),
                }
            if row.get(loc_name):
                loc = get_location(row[loc_name], domain=self.config['domain'])
                new_registered = _locations_per_type(self.config['domain'], 'PPS', loc)
                if new_registered > registered:
                    registered = new_registered
            values[month]['pps_ids'].add(row['pps_id'])

        rows = []
        total_row_values = defaultdict(int)
        months = sorted(set(month for month in values))
        for month in months:
            from custom.intrahealth.reports.utils import get_localized_months
            pps_ids = values[month]['pps_ids']
            unique = len(pps_ids)
            total_row_values['registered'] += registered
            total_row_values['unique'] += unique
            rows.append(
                [get_localized_months()[month - 1], registered, 0, unique, self.percent_fn(registered, unique),
                 unique, self.percent_fn(unique, unique)])
        self.total_row = ['', total_row_values['registered'], 0, total_row_values['unique'],
                          self.percent_fn(total_row_values['registered'], total_row_values['unique']),
                          total_row_values['unique'],
                          self.percent_fn(total_row_values['unique'], total_row_values['unique'])]
        return rows

    @property
    def headers(self):
        return DataTablesHeader(
            DataTablesColumn('Mois'),
            DataTablesColumn('No de PPS (number of PPS registered in that region)'),
            DataTablesColumn('No de PPS planifie (number of PPS planned)'),
            DataTablesColumn('No de PPS avec livrasion cet mois (number of PPS visited this month)'),
            DataTablesColumn('Taux de couverture (coverage ratio)'),
            DataTablesColumn('No de PPS avec donnees soumises (number of PPS which submitted data)'),
            DataTablesColumn('Exhaustivite des donnees'),
        )


class FicheData2(IntraHealthSqlData):
    slug = 'fiche_data'
    title = ''
    show_total = False
    product_names = set()

    @property
    def table_name(self):
        return get_table_name(self.config['domain'], OPERATEUR_COMBINED)

    @property
    def filters(self):
        filters = [BETWEEN("real_date_repeat", "startdate", "enddate")]
        loc_name = None
        if 'region_id' in self.config:
            loc_name = 'region_id'
        elif 'district_id' in self.config:
            loc_name = 'district_id'
        if loc_name:
            filters.append(EQ(loc_name, loc_name))
            if 'archived_locations' in self.config:
                filters.append(_locations_filter(self.config['archived_locations'], loc_name))
        return filters

    @property
    def group_by(self):
        group_by = ['product_name', 'pps_name']
        if 'region_id' in self.config:
            group_by.append("region_id")
        elif 'district_id' in self.config:
            group_by.append("district_id")
        return group_by

    @property
    def columns(self):
        columns = [
            DatabaseColumn('Product Name', SimpleColumn('product_name')),
            DatabaseColumn('LISTE des PPS', SimpleColumn('pps_name')),
            DatabaseColumn("Consommation Reelle", SumColumn('actual_consumption')),
            DatabaseColumn("Consommation Facturable", SumColumn('billed_consumption'))
        ]
        if 'district_id' in self.config:
            columns.append(DatabaseColumn('district_id', SimpleColumn('district_id')))
        elif 'region_id' in self.config:
            columns.append(DatabaseColumn('region_id', SimpleColumn('region_id')))
        return columns

    @property
    def total_row(self):
        return []

    @property
    def rows(self):
        product_names = set()
        pps_names = set()
        values = {}

        rows = self.get_data()
        for row in rows:
            pps_name = row['pps_name']
            product_name = row['product_name']
            pps_names.add(pps_name)
            product_names.add(product_name)
            if pps_name not in values:
                values[pps_name] = {}
            if product_name not in values[pps_name]:
                values[pps_name][product_name] = defaultdict(int)
            values[pps_name][product_name]['actual_consumption'] += 1
            values[pps_name][product_name]['billed_consumption'] += 1

        pps_names = sorted(pps_names)
        product_names = sorted(product_names)
        self.product_names = product_names
        rows = []
        for pps_name in pps_names:
            row = [pps_name]
            for product_name in product_names:
                values_for_product = values[pps_name][product_name] if \
                    product_name in values[pps_name] else {
                    'actual_consumption': 0,
                    'billed_consumption': 0,
                }
                actual_consumption = values_for_product['actual_consumption']
                billed_consumption = values_for_product['billed_consumption']
                row.append(actual_consumption)
                row.append(billed_consumption)
                row.append((actual_consumption or 0) - (billed_consumption or 0))
            rows.append(row)
        return rows

    @property
    def headers(self):
        headers = DataTablesHeader()
        headers.add_column(DataTablesColumnGroup('', DataTablesColumn('LISTE des PPS')))

        for product_name in self.product_names:
            headers.add_column(DataTablesColumnGroup(
                product_name,
                DataTablesColumn('Consommation Reelle'),
                DataTablesColumn('Consommation Facturable'),
                DataTablesColumn('Consommation Non Facturable')
            ))

        return headers


class DispDesProducts2(IntraHealthSqlData):
    slug = 'products'
    title = 'Taux de satisfaction de la commande de l\'operateur'
    show_total = False
    product_names = set()

    @property
    def table_name(self):
        return get_table_name(self.config['domain'], COMMANDE_COMBINED)

    @property
    def group_by(self):
        return ['productName']

    @property
    @memoized
    def products(self):
        return list(SQLProduct.objects.filter(domain=self.config['domain'], is_archived=False).order_by('name'))

    @property
    def columns(self):
        return [
            DatabaseColumn('Product Name', SimpleColumn('productName')),
            DatabaseColumn("Commandes", SumColumn('amountOrdered')),
            DatabaseColumn("Recu", SumColumn('amountReceived'))
        ]

    @property
    def total_row(self):
        return []

    @property
    def rows(self):
        product_names = set()
        products = self.products
        values = {
            product.name: [0, 0]
            for product in products
        }

        rows = self.get_data()
        for row in rows:
            productName = row['productName']
            product_names.add(productName)
            values[productName] = [
                row['amountOrdered']['html'],
                row['amountReceived']['html']
            ]

        commandes = ['Commandes']
        raux = ['Raux']
        taux = ['Taux']

        product_names = sorted(product_names)
        self.product_names = product_names
        for product_name in product_names:
            values_for_product = values[product_name]
            amountOrdered = values_for_product[0]
            amountReceived = values_for_product[1]
            commandes.append(amountOrdered)
            raux.append(amountReceived)
            taux.append("%d%%" % (100 * amountOrdered / (amountReceived or 1)))
        return [commandes, raux, taux]

    @property
    def headers(self):
        headers = DataTablesHeader(DataTablesColumn('Quantity'))
        for product_name in self.product_names:
            headers.add_column(DataTablesColumn(product_name))
        return headers


class ContainsFilter(SqlFilter):
    def __init__(self, column_name, contains):
        self.column_name = column_name
        self.contains = contains

    def build_expression(self):
        return sqlalchemy.column(self.column_name).like("%{0}%".format(self.contains))


class CustomEQFilter(SqlFilter):
    """
    EQ Filter without binding parameter
    """

    def __init__(self, column_name, parameter):
        self.column_name = column_name
        self.parameter = parameter

    def build_expression(self):
        return sqlalchemy.column(self.column_name).match(self.parameter)


class YeksiSqlData(SqlData):
    datatables = False
    show_charts = False
    show_total = True
    custom_total_calculate = False
    no_value = {'sort_key': 0, 'html': 0}
    fix_left_col = False

    @property
    def engine_id(self):
        return 'ucr'

    def percent_fn(self, x, y, nominal_denominator=1):
        return "{:.2f}%".format(100 * float(x or 0) / float(y or nominal_denominator))

    @property
    @memoized
    def months(self):
        return [month.date() for month in
                rrule(freq=MONTHLY, dtstart=self.config['startdate'], until=self.config['enddate'])]

    def date_in_selected_date_range(self, date):
        return self.months[0] <= date < self.months[-1] + relativedelta(months=1)

    def denominator_exists(self, denominator):
        return denominator and denominator['html']

    def get_index_of_month_in_selected_data_range(self, date):
        for index in range(len(self.months)):
            if date < self.months[index] + relativedelta(months=1):
                return index

    def cell_value_less_than(self, cell, value):
        return True if cell != 'pas de données' and float(cell[:-1]) < value else False

    def cell_value_bigger_than(self, cell, value):
        return True if cell != 'pas de données' and float(cell[:-1]) > value else False

    def month_headers(self):
        month_headers = []
        french_months = {
            1: 'Janvier',
            2: 'Février',
            3: 'Mars',
            4: 'Avril',
            5: 'Mai',
            6: 'Juin',
            7: 'Juillet',
            8: 'Août',
            9: 'Septembre',
            10: 'Octobre',
            11: 'Novembre',
            12: 'Décembre',
        }
        for month in self.months:
            month_headers.append(DataTablesColumn("{0} {1}".format(french_months[month.month], month.year)))
        return month_headers


class VisiteDeLOperateurDataSource(YeksiSqlData):

    @property
    def filters(self):
        filters = [BETWEEN("real_date", "startdate", "enddate")]
        program_id = self.config.get('program')
        if program_id:
            filters.append(ContainsFilter("select_programs", program_id))
        if 'region_id' in self.config and self.config['region_id']:
            filters.append(EQ("region_id", "region_id"))
        elif 'district_id' in self.config and self.config['district_id']:
            filters.append(EQ("district_id", "district_id"))
        elif 'pps_id' in self.config and self.config['pps_id']:
            filters.append(EQ("pps_id", "pps_id"))
        return filters

    @property
    def table_name(self):
        return get_table_name(self.config['domain'], YEKSI_NAA_REPORTS_VISITE_DE_L_OPERATOUR)

    @cached_property
    def loc_id(self):
        if 'pps_id' in self.config or 'district_id' in self.config:
            return 'pps_id'
        elif 'region_id' in self.config:
            return 'district_id'
        else:
            return 'region_id'

    @cached_property
    def loc_name(self):
        if 'pps_id' in self.config or 'district_id' in self.config:
            return 'pps_name'
        elif 'region_id' in self.config:
            return 'district_name'
        else:
            return 'region_name'

    @property
    def headers(self):
        if self.loc_id == 'pps_id':
            first_row = 'PPS'
        elif self.loc_id == 'district_id':
            first_row = 'District'
        else:
            first_row = 'Région'

        headers = DataTablesHeader(DataTablesColumn(first_row))
        for month in self.month_headers():
            headers.add_column(month)
        return headers


class VisiteDeLOperateurPerProductDataSource(YeksiSqlData):

    @property
    def filters(self):
        filters = [BETWEEN("real_date_repeat", "startdate", "enddate")]
        program_id = self.config.get('program')
        if program_id:
            programs = ProductsInProgramData(config={'domain': self.config['domain']}).rows
            for program in programs:
                if program_id == program[0]:
                    filters.append(OR(
                        [CustomEQFilter("product_id", product) for product in program[1].split(" ")]
                    ))
                    break
        if 'region_id' in self.config and self.config['region_id']:
            filters.append(EQ("region_id", "region_id"))
        elif 'district_id' in self.config and self.config['district_id']:
            filters.append(EQ("district_id", "district_id"))
        elif 'pps_id' in self.config and self.config['pps_id']:
            filters.append(EQ("pps_id", "pps_id"))
        return filters

    @property
    def table_name(self):
        return get_table_name(self.config['domain'], YEKSI_NAA_REPORTS_VISITE_DE_L_OPERATOUR_PER_PRODUCT)

    @cached_property
    def loc_id(self):
        if 'pps_id' in self.config or 'district_id' in self.config:
            return 'pps_id'
        elif 'region_id' in self.config:
            return 'district_id'
        else:
            return 'region_id'

    @cached_property
    def loc_name(self):
        if 'pps_id' in self.config or 'district_id' in self.config:
            return 'pps_name'
        elif 'region_id' in self.config:
            return 'district_name'
        else:
            return 'region_name'

    @property
    def headers(self):
        if self.loc_id == 'pps_id':
            first_row = 'PPS'
        elif self.loc_id == 'district_id':
            first_row = 'District'
        else:
            first_row = 'Région'

        headers = DataTablesHeader(DataTablesColumn(first_row))
        for month in self.month_headers():
            headers.add_column(month)
        return headers


class LogisticienDataSource(YeksiSqlData):

    @property
    def filters(self):
        filters = [BETWEEN("date_echeance", "startdate", "enddate")]
        if 'region_id' in self.config and self.config['region_id']:
            filters.append(EQ("region_id", "region_id"))
        elif 'district_id' in self.config and self.config['district_id']:
            filters.append(EQ("district_id", "district_id"))
        return filters

    @property
    def table_name(self):
        return get_table_name(self.config['domain'], YEKSI_NAA_REPORTS_LOGISTICIEN)

    @cached_property
    def loc_id(self):
        if 'region_id' in self.config:
            return 'district_id'
        else:
            return 'region_id'

    @cached_property
    def loc_name(self):
        if 'region_id' in self.config:
            return 'district_name'
        else:
            return 'region_name'

    @property
    def headers(self):
        if self.loc_id == 'district_id':
            first_row = 'District'
        else:
            first_row = 'Région'

        headers = DataTablesHeader(DataTablesColumn(first_row))
        for month in self.month_headers():
            headers.add_column(month)
        return headers


class ProgramsDataSource(YeksiSqlData):

    @property
    def filters(self):
        return []

    @property
    def table_name(self):
        return get_table_name(self.config['domain'], YEKSI_NAA_REPORTS_VISITE_DE_L_OPERATOUR_PER_PROGRAM)

    @property
    def headers(self):
        headers = DataTablesHeader(DataTablesColumn('ID'))
        headers.add_column(DataTablesColumn('Name'))
        return headers


class ProgramData(ProgramsDataSource):
    slug = 'program'
    comment = 'Program names'
    title = 'Program'
    show_total = False

    @property
    def group_by(self):
        group_by = ['program_id', 'program_name']
        return group_by

    @property
    def columns(self):
        columns = [
            DatabaseColumn("Program ID", SimpleColumn('program_id')),
            DatabaseColumn("Program Name", SimpleColumn('program_name')),
        ]
        return columns

    @property
    def rows(self):
        records = self.get_data()
        rows = []
        for record in records:
            program_name = record['program_name']
            if program_name != 'PLANNIFICATION FAMILIALE':
                rows.append([record['program_id'], record['program_name']])
        return sorted(rows, key=lambda x: x[0])


class ProductsDataSource(YeksiSqlData):

    @property
    def filters(self):
        return []

    @property
    def table_name(self):
        config_domain = self.config['domain']
        doc_id = StaticDataSourceConfiguration.get_doc_id(config_domain,
                                                          YEKSI_NAA_REPORTS_VISITE_DE_L_OPERATOUR_PER_PRODUCT)
        config, _ = get_datasource_config(doc_id, config_domain)
        return get_table_name(config_domain, config.table_id)

    @property
    def headers(self):
        headers = DataTablesHeader(DataTablesColumn('ID'))
        headers.add_column(DataTablesColumn('Name'))
        return headers


class ProductData(ProductsDataSource):
    slug = 'product'
    comment = 'Product names'
    title = 'Product'
    show_total = False

    @property
    def group_by(self):
        group_by = ['product_id', 'product_name']
        return group_by

    @property
    def columns(self):
        columns = [
            DatabaseColumn("Product ID", SimpleColumn('product_id')),
            DatabaseColumn("Product Name", SimpleColumn('product_name')),
        ]
        return columns

    @property
    def rows(self):
        records = self.get_data()
        return records


class ProductsInProgramData(ProgramsDataSource):
    """
    Returns list of all product ids used in program as string joined by spaces
    """
    slug = 'products_in_program'
    comment = 'Products selected per program'
    title = 'Products selected per program'
    show_total = False

    @property
    def group_by(self):
        group_by = ['program_id', 'product_ids']
        return group_by

    @property
    def columns(self):
        columns = [
            DatabaseColumn("Program ID", SimpleColumn('program_id')),
            DatabaseColumn("Product IDs", SimpleColumn('product_ids')),
        ]
        return columns

    @property
    def rows(self):
        records = self.get_data()
        programs = defaultdict(set)
        for record in records:
            product_ids = record['product_ids']
            program_id = record['program_id']
            if product_ids is not None:
                products = product_ids.split(' ')
                for product in products:
                    programs[program_id].add(product)
            else:
                programs[program_id].add(None)
        rows = []
        for program_id, products in programs.items():
            try:
                rows.append([program_id, " ".join(products)])
            except TypeError:
                rows.append([program_id, None])
        rows = sorted(rows, key=lambda x: x[0])
        return rows


class ProductsInProgramWithNameData(ProgramsDataSource):
    """
    Returns list of all product ids used in program as string joined by spaces
    """
    slug = 'products_in_program'
    comment = 'Products selected per program'
    title = 'Products selected per program'
    show_total = False

    @property
    def group_by(self):
        group_by = ['program_id', 'program_name', 'product_ids']
        return group_by

    @property
    def columns(self):
        columns = [
            DatabaseColumn("Program ID", SimpleColumn('program_id')),
            DatabaseColumn("Program Name", SimpleColumn('program_name')),
            DatabaseColumn("Product IDs", SimpleColumn('product_ids')),
        ]
        return columns

    @property
    def rows(self):
        records = self.get_data()
        programs = defaultdict()
        for record in records:
            product_ids = record['product_ids']
            program_id = record['program_id']
            program_name = record['program_name']
            programs[program_id] = {
                'name': program_name,
                'product_ids': [],
            }
            if product_ids is not None:
                products = product_ids.split(' ')
                for product in products:
                    programs[program_id]['product_ids'].append(product)
            else:
                programs[program_id]['product_ids'].append(None)
        rows = []
        for program_id, program_data in programs.items():
            program_name = program_data['name']
            if program_name == 'PLANNIFICATION FAMILIALE':
                program_name = 'PLANIFICATION FAMILIALE'
                program_id = '6844ee891e29f2df8493fe6c0e2c1837'
            rows.append({
                'program_id': program_id,
                'program_name': program_name,
                'product_ids': program_data['product_ids'],
            })
        return rows


class AvailabilityData(VisiteDeLOperateurDataSource):
    slug = 'disponibilite'
    comment = 'Disponibilité de la gamme au niveau PPS : combien de PPS ont eu tous les produits disponibles'
    title = 'Disponibilité'
    show_total = True
    custom_total_calculate = True

    def calculate_total_row(self, rows):
        total_row = [{
            'html': 'Disponibilité (%)',
        }]
        total_numerator = 0
        total_denominator = 0
        if self.loc_id == 'pps_id':
            data = {}
            for i in range(len(self.months)):
                data[i] = {
                    'pps_is_available': sum(
                        1 for pps_data in rows if pps_data[i + 1]['html'] == '100%'
                    ),
                    'pps_count': sum(1 for pps_data in rows
                                     if pps_data[i + 1]['html'] != 'pas de données')
                }
                if data[i]['pps_count']:
                    month_value = self.percent_fn(
                        data[i]['pps_is_available'],
                        data[i]['pps_count']
                    )
                    total_row.append({
                        'html': month_value,
                        'style': 'color: red' if self.cell_value_less_than(month_value, 95) else '',
                    })
                    total_numerator += data[i]['pps_is_available']
                    total_denominator += data[i]['pps_count']
                else:
                    total_row.append({
                        'html': 'pas de données',
                    })
            if total_denominator:
                total_value = self.percent_fn(
                    total_numerator,
                    total_denominator
                )
                total_row.append({
                    'html': total_value,
                    'style': 'color: red' if self.cell_value_less_than(total_value, 95) else '',
                })
            else:
                total_row.append({
                    'html': 'pas de données',
                })
        else:
            for i in range(len(self.months)):
                numerator = 0
                denominator = 0
                for location in rows:
                    numerator += sum(rows[location][i].values())
                    denominator += len(rows[location][i])
                total_numerator += numerator
                total_denominator += denominator
                if denominator:
                    month_value = self.percent_fn(numerator, denominator)
                    total_row.append({
                        'html': month_value,
                        'style': 'color: red' if self.cell_value_less_than(month_value, 95) else '',
                    })
                else:
                    total_row.append({
                        'html': 'pas de données',
                    })
            if total_denominator:
                total_value = self.percent_fn(total_numerator, total_denominator)
                total_row.append({
                    'html': total_value,
                    'style': 'color: red' if self.cell_value_less_than(total_value, 95) else '',
                })
            else:
                total_row.append({
                    'html': 'pas de données',
                })
        return total_row

    @property
    def group_by(self):
        group_by = ['real_date', 'pps_id', self.loc_name]
        if self.loc_id != 'pps_id':
            group_by.append(self.loc_id)
        return group_by

    @property
    def columns(self):
        columns = [
            DatabaseColumn("PPS ID", SimpleColumn('pps_id')),
            DatabaseColumn("Date", SimpleColumn('real_date')),
            DatabaseColumn("Number of PPS with stockout", MaxColumn('pps_is_outstock')),
        ]
        if self.loc_id == 'pps_id':
            columns.append(DatabaseColumn("PPS Name", SimpleColumn('pps_name')))
        elif self.loc_id == 'district_id':
            columns.append(DatabaseColumn("District ID", SimpleColumn('district_id')))
            columns.append(DatabaseColumn("District Name", SimpleColumn('district_name')))
        else:
            columns.append(DatabaseColumn("Region ID", SimpleColumn('region_id')))
            columns.append(DatabaseColumn("Region Name", SimpleColumn('region_name')))
        return columns

    def get_availability_data_per_month_per_pps(self, records):
        data = {}
        loc_names = {}
        for record in records:
            if not self.date_in_selected_date_range(record['real_date']):
                continue
            if record[self.loc_id] not in data:
                data[record[self.loc_id]] = ['pas de données'] * len(self.months)
                loc_names[record[self.loc_id]] = record[self.loc_name]
            month_index = self.get_index_of_month_in_selected_data_range(record['real_date'])
            data[record[self.loc_id]][month_index] = '0%' if record['pps_is_outstock']['html'] == 1 else '100%'
        return loc_names, data

    def get_availability_data_per_month_aggregated(self, records):
        data = defaultdict(list)
        loc_names = {}
        new_data = {}
        for record in records:
            if not self.date_in_selected_date_range(record['real_date']):
                continue
            if record[self.loc_id] not in data:
                for i in range(len(self.months)):
                    data[record[self.loc_id]].append(defaultdict(int))
                loc_names[record[self.loc_id]] = record[self.loc_name]
            month_index = self.get_index_of_month_in_selected_data_range(record['real_date'])
            no_multiple_rows_per_pps_in_month = \
                data[record[self.loc_id]][month_index].get(record['pps_id']) is None
            if no_multiple_rows_per_pps_in_month or \
                data[record[self.loc_id]][month_index][record['pps_id']] == 1:
                data[record[self.loc_id]][month_index][record['pps_id']] = 0 if \
                    record['pps_is_outstock']['html'] == 1 else 1

        for location in data:
            new_data[location] = ['pas de données'] * len(self.months)
            for month_index in range(len(self.months)):
                if data[location][month_index]:
                    new_data[location][month_index] = self.percent_fn(
                        sum(data[location][month_index].values()),
                        len(data[location][month_index])
                    )
        return loc_names, new_data, data

    def get_average_availability_in_location(self, data_per_localization):
        numerator = 0
        denominator = 0
        for data_in_month in data_per_localization:
            if data_in_month and data_in_month != 'pas de données':
                if self.loc_id == 'pps_id':
                    if data_in_month == '100%':
                        numerator += 1
                else:
                    numerator += float(data_in_month[:-1])
                denominator += 1
        if denominator:
            if self.loc_id == 'pps_id':
                return "{:.2f}%".format(numerator * 100 / denominator)
            else:
                return "{:.2f}%".format(numerator / denominator)
        else:
            return 'pas de données'

    def parse_availability_data_to_rows(self, loc_names, data):
        rows = []
        for loc_id in data:
            row = [{
                'html': loc_names[loc_id],
            }]
            for cell in data[loc_id]:
                row.append({
                    'html': cell,
                    'style': 'color: red' if self.cell_value_less_than(cell, 95) else '',
                })
            average = self.get_average_availability_in_location(data[loc_id])
            row.append({
                'html': average,
                'style': 'color: red' if self.cell_value_less_than(average, 95) else '',
            })
            rows.append(row)
        return rows

    @property
    def rows(self):
        records = self.get_data()

        if self.loc_id == 'pps_id':
            loc_names, data = self.get_availability_data_per_month_per_pps(records)
        else:
            loc_names, data, tmp = self.get_availability_data_per_month_aggregated(records)
            self.total_row = self.calculate_total_row(tmp)

        rows = self.parse_availability_data_to_rows(loc_names, data)
        if self.loc_id == 'pps_id':
            self.total_row = self.calculate_total_row(rows)
        return sorted(rows, key=lambda x: x[0]['html'])

    @property
    def headers(self):
        headers = super(AvailabilityData, self).headers
        headers.add_column(DataTablesColumn('Taux moyen de disponibilité'))
        return headers


class LossRateData(VisiteDeLOperateurPerProductDataSource):
    slug = 'taux_de_perte'
    comment = 'Taux de Perte (hors péremption)'
    title = 'Taux de Perte (hors péremption)'
    show_total = True
    custom_total_calculate = True

    def calculate_total_row(self, data):
        if 'region_id' in self.config and self.config['region_id']:
            total_row = [{
                'html': 'Taux par Région',
            }]
        elif 'district_id' in self.config and self.config['district_id']:
            total_row = [{
                'html': 'Taux par District',
            }]
        elif 'pps_id' in self.config and self.config['pps_id']:
            total_row = [{
                'html': '',
            }]
        else:
            total_row = [{
                'html': 'Taux par Pays',
            }]
        total_numerator = 0
        total_denominator = 0
        for i in range(len(self.months)):
            numerator = sum(
                data[loc_id][i]['loss_amt'] for loc_id in data if
                data[loc_id][i]['final_pna_stock']
            )
            denominator = sum(
                data[loc_id][i]['final_pna_stock'] for loc_id in data if
                data[loc_id][i]['final_pna_stock']
            )
            total_numerator += numerator
            total_denominator += denominator
            total_value = self.percent_fn(
                numerator,
                denominator
            )
            if denominator:
                total_row.append({
                    'html': total_value,
                })
            else:
                total_row.append({
                    'html': 'pas de données',
                })
        total_value = self.percent_fn(
            total_numerator,
            total_denominator
        )
        if total_denominator:
            total_row.append({
                'html': total_value,
            })
        else:
            total_row.append({
                'html': 'pas de données',
            })
        return total_row

    @property
    def group_by(self):
        return ['real_date_repeat', self.loc_id, self.loc_name]

    @property
    def columns(self):
        columns = [
            DatabaseColumn("Date", SimpleColumn('real_date_repeat')),
            DatabaseColumn("Total number of PNA lost product", SumColumn('loss_amt')),
            DatabaseColumn("PNA final stock", SumColumn('final_pna_stock')),
        ]
        if self.loc_id == 'pps_id':
            columns.append(DatabaseColumn("PPS ID", SimpleColumn('pps_id')))
            columns.append(DatabaseColumn("PPS Name", SimpleColumn('pps_name')))
        elif self.loc_id == 'district_id':
            columns.append(DatabaseColumn("District ID", SimpleColumn('district_id')))
            columns.append(DatabaseColumn("District Name", SimpleColumn('district_name')))
        else:
            columns.append(DatabaseColumn("Region ID", SimpleColumn('region_id')))
            columns.append(DatabaseColumn("Region Name", SimpleColumn('region_name')))
        return columns

    def get_average_loss_rate_in_location(self, data_per_localization):
        numerator = 0
        denominator = 0
        for data_in_month in data_per_localization:
            if data_in_month and data_in_month['final_pna_stock']:
                numerator += data_in_month['loss_amt']
                denominator += data_in_month['final_pna_stock']
        if denominator:
            value = self.percent_fn(
                numerator,
                denominator,
            )
            return {
                'html': value,
            }
        else:
            return {
                'html': 'pas de données',
            }

    def parse_loss_rate_to_rows(self, loc_names, data):
        rows = []
        for loc_id in data:
            row = [{
                'html': loc_names[loc_id],
            }]
            for i in range(len(self.months)):
                if data[loc_id][i]['final_pna_stock']:
                    month_value = self.percent_fn(
                        data[loc_id][i]['loss_amt'],
                        data[loc_id][i]['final_pna_stock']
                    )
                    row.append({
                        'html': month_value,
                    })
                else:
                    row.append({
                        'html': 'pas de données',
                    })
            row.append(self.get_average_loss_rate_in_location(data[loc_id]))
            rows.append(row)
        return rows

    def get_loss_rate_per_month(self, records):
        data = defaultdict(list)
        loc_names = {}
        for record in records:
            if not self.date_in_selected_date_range(record['real_date_repeat']):
                continue
            if record[self.loc_id] not in data:
                for i in range(len(self.months)):
                    data[record[self.loc_id]].append(defaultdict(int))
                loc_names[record[self.loc_id]] = record[self.loc_name]
            month_index = self.get_index_of_month_in_selected_data_range(record['real_date_repeat'])
            if self.denominator_exists(record['final_pna_stock']):
                if record['loss_amt']:
                    data[record[self.loc_id]][month_index]['loss_amt'] += record['loss_amt']['html']
                data[record[self.loc_id]][month_index]['final_pna_stock'] += record['final_pna_stock']['html']
        return loc_names, data

    @property
    def rows(self):
        records = self.get_data()
        loc_names, data = self.get_loss_rate_per_month(records)
        self.total_row = self.calculate_total_row(data)
        rows = self.parse_loss_rate_to_rows(loc_names, data)
        return sorted(rows, key=lambda x: x[0]['html'])

    @property
    def headers(self):
        headers = super(LossRateData, self).headers
        headers.add_column(DataTablesColumn('Taux moyen'))
        return headers


class ExpirationRateData(VisiteDeLOperateurPerProductDataSource):
    slug = 'taux_de_peremption'
    comment = 'valeur péremption sur valeur totale'
    title = 'Taux de Péremption'
    show_total = True
    custom_total_calculate = True

    def calculate_total_row(self, data):
        if 'region_id' in self.config and self.config['region_id']:
            total_row = [{
                'html': 'Taux par Région',
            }]
        elif 'district_id' in self.config and self.config['district_id']:
            total_row = [{
                'html': 'Taux par District',
            }]
        elif 'pps_id' in self.config and self.config['pps_id']:
            total_row = [{
                'html': '',
            }]
        else:
            total_row = [{
                'html': 'Taux par Pays',
            }]
        total_numerator = 0
        total_denominator = 0
        for i in range(len(self.months)):
            numerator = sum(
                data[loc_id][i]['expired_pna_valuation'] for loc_id in data if
                data[loc_id][i]['final_pna_stock_valuation']
            )
            denominator = sum(
                data[loc_id][i]['final_pna_stock_valuation'] for loc_id in data if
                data[loc_id][i]['final_pna_stock_valuation']
            )
            total_numerator += numerator
            total_denominator += denominator
            total_value = self.percent_fn(
                numerator,
                denominator
            )
            if denominator:
                total_row.append({
                    'html': total_value,
                    'style': 'color: red' if self.cell_value_bigger_than(total_value, 5) else '',
                })
            else:
                total_row.append({
                    'html': 'pas de données',
                })
        total_value = self.percent_fn(
            total_numerator,
            total_denominator
        )
        if total_denominator:
            total_row.append({
                'html': total_value,
                'style': 'color: red' if self.cell_value_bigger_than(total_value, 5) else '',
            })
        else:
            total_row.append({
                'html': 'pas de données',
            })
        return total_row

    @property
    def group_by(self):
        return ['real_date_repeat', self.loc_id, self.loc_name]

    @property
    def columns(self):
        columns = [
            DatabaseColumn("Date", SimpleColumn('real_date_repeat')),
            DatabaseColumn("Expired products valuation", SumColumn('expired_pna_valuation')),
            DatabaseColumn("Products stock valuation", SumColumn('final_pna_stock_valuation')),
        ]
        if self.loc_id == 'pps_id':
            columns.append(DatabaseColumn("PPS ID", SimpleColumn('pps_id')))
            columns.append(DatabaseColumn("PPS Name", SimpleColumn('pps_name')))
        elif self.loc_id == 'district_id':
            columns.append(DatabaseColumn("District ID", SimpleColumn('district_id')))
            columns.append(DatabaseColumn("District Name", SimpleColumn('district_name')))
        else:
            columns.append(DatabaseColumn("Region ID", SimpleColumn('region_id')))
            columns.append(DatabaseColumn("Region Name", SimpleColumn('region_name')))
        return columns

    def get_average_expiration_rate_in_location(self, data_per_localization):
        numerator = 0
        denominator = 0
        for data_in_month in data_per_localization:
            if data_in_month and data_in_month['final_pna_stock_valuation']:
                numerator += data_in_month['expired_pna_valuation']
                denominator += data_in_month['final_pna_stock_valuation']
        if denominator:
            value = self.percent_fn(
                numerator,
                denominator,
            )
            return {
                'html': value,
                'style': 'color: red' if self.cell_value_bigger_than(value, 5) else '',
            }
        else:
            return {
                'html': 'pas de données',
            }

    def parse_expiration_rate_to_rows(self, loc_names, data):
        rows = []
        for loc_id in data:
            row = [{
                'html': loc_names[loc_id],
            }]
            for i in range(len(self.months)):
                if data[loc_id][i]['final_pna_stock_valuation']:
                    month_value = self.percent_fn(
                        data[loc_id][i]['expired_pna_valuation'],
                        data[loc_id][i]['final_pna_stock_valuation']
                    )
                    row.append({
                        'html': month_value,
                        'style': 'color: red' if self.cell_value_bigger_than(month_value, 5) else '',
                    })
                else:
                    row.append({
                        'html': 'pas de données',
                    })
            row.append(self.get_average_expiration_rate_in_location(data[loc_id]))
            rows.append(row)
        return rows

    def get_expiration_rate_per_month(self, records):
        data = defaultdict(list)
        loc_names = {}
        for record in records:
            if not self.date_in_selected_date_range(record['real_date_repeat']):
                continue
            if record[self.loc_id] not in data:
                for i in range(len(self.months)):
                    data[record[self.loc_id]].append(defaultdict(int))
                loc_names[record[self.loc_id]] = record[self.loc_name]
            month_index = self.get_index_of_month_in_selected_data_range(record['real_date_repeat'])
            if self.denominator_exists(record['final_pna_stock_valuation']):
                if record['expired_pna_valuation']:
                    data[record[self.loc_id]][month_index]['expired_pna_valuation'] += \
                        record['expired_pna_valuation']['html']
                data[record[self.loc_id]][month_index]['final_pna_stock_valuation'] += \
                    record['final_pna_stock_valuation']['html']
        return loc_names, data

    @property
    def rows(self):
        records = self.get_data()
        loc_names, data = self.get_expiration_rate_per_month(records)
        self.total_row = self.calculate_total_row(data)
        rows = self.parse_expiration_rate_to_rows(loc_names, data)
        return sorted(rows, key=lambda x: x[0]['html'])

    @property
    def headers(self):
        headers = super(ExpirationRateData, self).headers
        headers.add_column(DataTablesColumn('Taux moyen'))
        return headers


class RecoveryRateByPPSData(VisiteDeLOperateurDataSource):
    slug = 'taux_de_recouvrement_au_niveau_du_pps'
    comment = 'Somme des montants payés sur total dû'
    title = 'Taux de Recouvrement au niveau du PPS'
    show_total = True
    custom_total_calculate = True

    def calculate_total_row(self, data, value_partials):
        if 'region_id' in self.config and self.config['region_id']:
            total_row = [{
                'html': 'Taux par Région',
            }]
        elif 'district_id' in self.config and self.config['district_id']:
            total_row = [{
                'html': 'Taux par District',
            }]
        elif 'pps_id' in self.config and self.config['pps_id']:
            total_row = [{
                'html': 'Taux par PPS',
            }]
        else:
            total_row = [{
                'html': 'Taux par Pays',
            }]
        for i in range(len(self.months)):
            numerator = sum(
                data[loc_id][i]['pps_total_amt_paid'] for loc_id in data
            )
            denominator = sum(
                data[loc_id][i]['delivery_amt_owed'] + data[loc_id][i]['pps_total_amt_owed'] -
                data[loc_id][i]['delivery_amt_owed_first_visit'] for loc_id in data
            )
            total_value = self.percent_fn(
                numerator,
                denominator,
                nominal_denominator=100,
            )
            if denominator or numerator:
                total_row.append({
                    'html': total_value,
                })
            else:
                total_row.append({
                    'html': 'pas de données',
                })
        total_numerator = 0
        total_denominator = 0
        for loc_id, value in value_partials.items():
            total_numerator += value['numerator']
            total_denominator += value['denominator']
        total_value = self.percent_fn(
            total_numerator,
            total_denominator,
            nominal_denominator=100,
        )
        if total_denominator or total_numerator:
            total_row.append({
                'html': total_value,
            })
        else:
            total_row.append({
                'html': 'pas de données',
            })
        return total_row

    @property
    def group_by(self):
        group_by = [
            'doc_id', 'real_date_precise', 'delivery_amt_owed', 'pps_id', self.loc_name, 'pps_total_amt_paid',
            'pps_total_amt_owed'
        ]
        if self.loc_id != 'pps_id':
            group_by.append(self.loc_id)
        return group_by

    @property
    def columns(self):
        columns = [
            DatabaseColumn("PPS ID", SimpleColumn('pps_id')),
            DatabaseColumn("Date", SimpleColumn('real_date_precise')),
            DatabaseColumn("Delivery Amount Owed", SimpleColumn('delivery_amt_owed')),
            DatabaseColumn("Total amount paid by PPS", SimpleColumn('pps_total_amt_paid')),
            DatabaseColumn("Total amount owed by PPS", SimpleColumn('pps_total_amt_owed')),
        ]
        if self.loc_id == 'pps_id':
            columns.append(DatabaseColumn("PPS Name", SimpleColumn('pps_name')))
        elif self.loc_id == 'district_id':
            columns.append(DatabaseColumn("District ID", SimpleColumn('district_id')))
            columns.append(DatabaseColumn("District Name", SimpleColumn('district_name')))
        else:
            columns.append(DatabaseColumn("Region ID", SimpleColumn('region_id')))
            columns.append(DatabaseColumn("Region Name", SimpleColumn('region_name')))
        return columns

    def get_recovery_rate_by_pps_in_location(self, data_per_localization):
        numerator = 0
        denominator = 0
        value_partials = {
            'numerator': 0,
            'denominator': 0,
        }
        first_data = True
        for data_in_month in data_per_localization:
            if data_in_month and data_in_month['delivery_amt_owed']:
                numerator += data_in_month['pps_total_amt_paid']
                denominator += data_in_month['delivery_amt_owed']
                if first_data:
                    first_data = False
                    denominator += data_in_month['pps_total_amt_owed']
                    denominator -= data_in_month['delivery_amt_owed_first_visit']
        if denominator or numerator:
            value = self.percent_fn(
                numerator,
                denominator,
                nominal_denominator=100,
            )
            value_partials['numerator'] = numerator
            value_partials['denominator'] = denominator
            return {'html': value}, value_partials
        else:
            return {'html': 'pas de données'}, value_partials

    def parse_recovery_rate_by_pps_to_rows(self, loc_names, data):
        rows = []
        value_partials = {}
        for loc_id in data:
            row = [{
                'html': loc_names[loc_id],
            }]
            for i in range(len(self.months)):
                denominator = \
                    data[loc_id][i]['delivery_amt_owed'] + \
                    data[loc_id][i]['pps_total_amt_owed'] - \
                    data[loc_id][i]['delivery_amt_owed_first_visit']
                if denominator or data[loc_id][i]['pps_total_amt_paid']:
                    month_value = self.percent_fn(
                        data[loc_id][i]['pps_total_amt_paid'],
                        denominator,
                        nominal_denominator=100,
                    )
                    row.append({
                        'html': month_value,
                    })
                else:
                    row.append({
                        'html': 'pas de données',
                    })
            cell, value_partials_per_loc_id = self.get_recovery_rate_by_pps_in_location(data[loc_id])
            row.append(cell)
            value_partials[loc_id] = value_partials_per_loc_id
            rows.append(row)
        return rows, value_partials

    def aggregate_recovery_rate_by_pps_per_month_from_pps_to_higher_location(self, data, pps_id_per_higher_loc_id):
        agg_data = {}
        for pps_id, values in data.items():
            higher_loc_id = pps_id_per_higher_loc_id[pps_id]
            if higher_loc_id not in agg_data:
                agg_data[higher_loc_id] = []
                for i in range(len(self.months)):
                    agg_data[higher_loc_id].append({
                        'delivery_amt_owed_first_visit': 0,
                        'pps_total_amt_owed': 0,
                        'pps_total_amt_paid': 0,
                        'delivery_amt_owed': 0,
                    })
            for month_index in range(len(self.months)):
                agg_data[higher_loc_id][month_index]['delivery_amt_owed_first_visit'] += \
                    values[month_index]['delivery_amt_owed_first_visit']
                agg_data[higher_loc_id][month_index]['pps_total_amt_owed'] += \
                    values[month_index]['pps_total_amt_owed']
                agg_data[higher_loc_id][month_index]['pps_total_amt_paid'] += \
                    values[month_index]['pps_total_amt_paid']
                agg_data[higher_loc_id][month_index]['delivery_amt_owed'] += \
                    values[month_index]['delivery_amt_owed']
        return agg_data

    def get_recovery_rate_by_pps_per_month(self, records):
        data = {}
        loc_names = {}
        pps_id_per_higher_loc_id = {}
        for record in records:
            if not self.date_in_selected_date_range(record['real_date_precise']):
                continue
            if record['pps_id'] not in data:
                data[record['pps_id']] = []
                for i in range(len(self.months)):
                    data[record['pps_id']].append({
                        'delivery_amt_owed_first_visit': 0,
                        'real_date_precise_first': None,
                        'pps_total_amt_owed': 0,
                        'pps_total_amt_paid': 0,
                        'delivery_amt_owed': 0,
                    })
                if self.loc_id == 'pps_id':
                    loc_names[record[self.loc_id]] = record[self.loc_name]
                else:
                    if record[self.loc_id] not in loc_names:
                        loc_names[record[self.loc_id]] = record[self.loc_name]
                    pps_id_per_higher_loc_id[record['pps_id']] = record[self.loc_id]
            month_index = self.get_index_of_month_in_selected_data_range(record['real_date_precise'])
            if record.get('delivery_amt_owed') is not None:
                if data[record['pps_id']][month_index]['real_date_precise_first'] is None or \
                    record['real_date_precise'] < \
                    data[record['pps_id']][month_index]['real_date_precise_first']:
                    data[record['pps_id']][month_index]['pps_total_amt_owed'] = record['pps_total_amt_owed']
                    data[record['pps_id']][month_index]['real_date_precise_first'] = \
                        record['real_date_precise']
                    data[record['pps_id']][month_index]['delivery_amt_owed_first_visit'] = \
                        record['delivery_amt_owed']
                if record['pps_total_amt_paid']:
                    data[record['pps_id']][month_index]['pps_total_amt_paid'] += record['pps_total_amt_paid']
                data[record['pps_id']][month_index]['delivery_amt_owed'] += record['delivery_amt_owed']
        if self.loc_id != 'pps_id':
            agg_data = self.aggregate_recovery_rate_by_pps_per_month_from_pps_to_higher_location(
                data, pps_id_per_higher_loc_id)
            return loc_names, agg_data
        return loc_names, data

    @property
    def rows(self):
        records = self.get_data()
        loc_names, data = self.get_recovery_rate_by_pps_per_month(records)
        rows, value_partials = self.parse_recovery_rate_by_pps_to_rows(loc_names, data)
        self.total_row = self.calculate_total_row(data, value_partials)
        return sorted(rows, key=lambda x: x[0]['html'])

    @property
    def headers(self):
        headers = super(RecoveryRateByPPSData, self).headers
        headers.add_column(DataTablesColumn('Taux moyen'))
        return headers


class RecoveryRateByDistrictData(LogisticienDataSource):
    slug = 'taux_de_recouvrement_au_niveau_du_district'
    comment = 'Somme des montants payés sur total dû'
    title = 'Taux de Recouvrement au niveau du District'
    show_total = True
    custom_total_calculate = True

    def calculate_total_row(self, data):
        if 'region_id' in self.config and self.config['region_id']:
            total_row = [{
                'html': 'Taux par Région',
            }]
        elif 'district_id' in self.config and self.config['district_id']:
            total_row = [{
                'html': 'Taux par District',
            }]
        else:
            total_row = [{
                'html': 'Taux par Pays',
            }]
        total_numerator = 0
        total_denominator = 0
        for i in range(len(self.months)):
            numerator = sum(
                data[loc_id][i]['montant_paye'] for loc_id in data if
                data[loc_id][i]['montant_reel_a_payer']
            )
            denominator = sum(
                data[loc_id][i]['montant_reel_a_payer'] for loc_id in data if
                data[loc_id][i]['montant_reel_a_payer']
            )
            total_numerator += numerator
            total_denominator += denominator
            total_value = self.percent_fn(
                numerator,
                denominator
            )
            if denominator:
                total_row.append({
                    'html': total_value,
                })
            else:
                total_row.append({
                    'html': 'pas de données',
                })
        total_value = self.percent_fn(
            total_numerator,
            total_denominator
        )
        if total_denominator:
            total_row.append({
                'html': total_value,
            })
        else:
            total_row.append({
                'html': 'pas de données',
            })
        return total_row

    @property
    def group_by(self):
        return ['date_echeance', 'district_id', 'district_name']

    @property
    def columns(self):
        columns = [
            DatabaseColumn("District ID", SimpleColumn('district_id')),
            DatabaseColumn("District Name", SimpleColumn('district_name')),
            DatabaseColumn("Date", SimpleColumn('date_echeance')),
            DatabaseColumn("Sum of the amounts paid by the district", SumColumn('montant_paye')),
            DatabaseColumn("Total amount owed by the district to PNA", SumColumn('montant_reel_a_payer')),
        ]
        return columns

    def get_recovery_rate_by_district_in_location(self, data_per_localization):
        numerator = 0
        denominator = 0
        for data_in_month in data_per_localization:
            if data_in_month and data_in_month['montant_reel_a_payer']:
                numerator += data_in_month['montant_paye']
                denominator += data_in_month['montant_reel_a_payer']
        if denominator:
            value = self.percent_fn(
                numerator,
                denominator,
            )
            return {
                'html': value,
            }
        else:
            return {
                'html': 'pas de données',
            }

    def parse_recovery_rate_by_district_to_rows(self, loc_names, data):
        rows = []
        for loc_id in data:
            row = [{
                'html': loc_names[loc_id],
            }]
            for i in range(len(self.months)):
                if data[loc_id][i]['montant_reel_a_payer']:
                    month_value = self.percent_fn(
                        data[loc_id][i]['montant_paye'],
                        data[loc_id][i]['montant_reel_a_payer']
                    )
                    row.append({
                        'html': month_value,
                    })
                else:
                    row.append({
                        'html': 'pas de données',
                    })
            row.append(self.get_recovery_rate_by_district_in_location(data[loc_id]))
            rows.append(row)
        return rows

    def get_recovery_rate_by_district_per_month(self, records):
        data = defaultdict(list)
        loc_names = {}
        for record in records:
            if not self.date_in_selected_date_range(record['date_echeance']):
                continue
            if record['district_id'] not in data:
                for i in range(len(self.months)):
                    data[record['district_id']].append(defaultdict(int))
                loc_names[record['district_id']] = record['district_name']
            month_index = self.get_index_of_month_in_selected_data_range(record['date_echeance'])
            if self.denominator_exists(record['montant_reel_a_payer']):
                if record['montant_paye']:
                    data[record['district_id']][month_index]['montant_paye'] += \
                        record['montant_paye']['html']
                data[record['district_id']][month_index]['montant_reel_a_payer'] += \
                    record['montant_reel_a_payer']['html']
        return loc_names, data

    @property
    def rows(self):
        records = self.get_data()
        district_names, data = self.get_recovery_rate_by_district_per_month(records)
        self.total_row = self.calculate_total_row(data)
        rows = self.parse_recovery_rate_by_district_to_rows(district_names, data)
        return sorted(rows, key=lambda x: x[0]['html'])

    @property
    def headers(self):
        headers = super(RecoveryRateByDistrictData, self).headers
        headers.add_column(DataTablesColumn('Taux moyen'))
        return headers


class RuptureRateByPPSData(VisiteDeLOperateurDataSource):
    slug = 'taux_de_rupture_par_pps'
    comment = 'Nombre de produits en rupture sur le nombre total de produits du PPS'
    title = 'Taux de Rupture par PPS'
    show_total = True
    custom_total_calculate = True

    def calculate_total_row(self, data):
        if 'region_id' in self.config and self.config['region_id']:
            total_row = [{
                'html': 'Taux par Région',
            }]
        elif 'district_id' in self.config and self.config['district_id']:
            total_row = [{
                'html': 'Taux par District',
            }]
        elif 'pps_id' in self.config and self.config['pps_id']:
            total_row = [{
                'html': '',
            }]
        else:
            total_row = [{
                'html': 'Taux par Pays',
            }]
        total_numerator = 0
        total_denominator = 0
        for i in range(len(self.months)):
            numerator = sum(
                data[loc_id][i]['nb_products_stockout'] for loc_id in data if
                data[loc_id][i]['count_products_select']
            )
            denominator = sum(
                data[loc_id][i]['count_products_select'] for loc_id in data if
                data[loc_id][i]['count_products_select']
            )
            total_numerator += numerator
            total_denominator += denominator
            total_value = self.percent_fn(
                numerator,
                denominator
            )
            if denominator:
                total_row.append({
                    'html': total_value,
                    'style': 'color: red' if self.cell_value_bigger_than(total_value, 2) else '',
                })
            else:
                total_row.append({
                    'html': 'pas de données',
                })
        total_value = self.percent_fn(
            total_numerator,
            total_denominator
        )
        if total_denominator:
            total_row.append({
                'html': total_value,
                'style': 'color: red' if self.cell_value_bigger_than(total_value, 2) else '',
            })
        else:
            total_row.append({
                'html': 'pas de données',
            })
        return total_row

    @property
    def group_by(self):
        return ['doc_id', 'real_date', 'pps_id', 'pps_name', 'nb_products_stockout', 'count_products_select']

    @property
    def columns(self):
        columns = [
            DatabaseColumn("PPS ID", SimpleColumn('pps_id')),
            DatabaseColumn("PPS Name", SimpleColumn('pps_name')),
            DatabaseColumn("Date", SimpleColumn('real_date')),
            DatabaseColumn("Number of stockout products", SimpleColumn('nb_products_stockout')),
            DatabaseColumn("Number of products in pps", SimpleColumn('count_products_select')),
        ]
        return columns

    def get_average_rupture_rate_in_location(self, data_per_localization):
        numerator = 0
        denominator = 0
        for data_in_month in data_per_localization:
            if data_in_month and data_in_month['count_products_select']:
                numerator += data_in_month['nb_products_stockout']
                denominator += data_in_month['count_products_select']
        if denominator:
            value = self.percent_fn(
                numerator,
                denominator,
            )
            return {
                'html': value,
                'style': 'color: red' if self.cell_value_bigger_than(value, 2) else '',
            }
        else:
            return {
                'html': 'pas de données',
            }

    def parse_rupture_rate_to_rows(self, pps_names, data):
        rows = []
        for pps_id in data:
            row = [{
                'html': pps_names[pps_id],
            }]
            for i in range(len(self.months)):
                if data[pps_id][i]['count_products_select']:
                    month_value = self.percent_fn(
                        data[pps_id][i]['nb_products_stockout'],
                        data[pps_id][i]['count_products_select']
                    )
                    row.append({
                        'html': month_value,
                        'style': 'color: red' if self.cell_value_bigger_than(month_value, 2) else '',
                    })
                else:
                    row.append({
                        'html': 'pas de données',
                    })
            row.append(self.get_average_rupture_rate_in_location(data[pps_id]))
            rows.append(row)
        return rows

    def get_rupture_rate_per_month(self, records):
        data = defaultdict(list)
        pps_names = {}
        for record in records:
            if not self.date_in_selected_date_range(record['real_date']):
                continue
            if record['pps_id'] not in data:
                for i in range(len(self.months)):
                    data[record['pps_id']].append(defaultdict(int))
                pps_names[record['pps_id']] = record['pps_name']
            month_index = self.get_index_of_month_in_selected_data_range(record['real_date'])
            if record['count_products_select']:
                if record['nb_products_stockout']:
                    data[record['pps_id']][month_index]['nb_products_stockout'] += \
                        record['nb_products_stockout']
                data[record['pps_id']][month_index]['count_products_select'] += record['count_products_select']
        return pps_names, data

    @property
    def rows(self):
        records = self.get_data()
        pps_names, data = self.get_rupture_rate_per_month(records)
        self.total_row = self.calculate_total_row(data)
        rows = self.parse_rupture_rate_to_rows(pps_names, data)
        return sorted(rows, key=lambda x: x[0]['html'])

    @cached_property
    def loc_id(self):
        return 'pps_id'

    @property
    def headers(self):
        headers = super(RuptureRateByPPSData, self).headers
        headers.add_column(DataTablesColumn('Taux moyen'))
        return headers


class SatisfactionRateAfterDeliveryData(VisiteDeLOperateurPerProductDataSource):
    slug = 'taux_de_satisfaction_apres_livraison'
    comment = 'produits proposés sur produits livrés'
    title = 'Taux de satisfaction (après livraison)'
    show_total = True
    custom_total_calculate = True

    def calculate_total_row(self, products):
        total_row = ['Total (%)']
        for i in range(len(self.months)):
            numerator = sum(
                products[product_id][i]['amt_delivered_convenience'] for product_id in products if
                products[product_id][i]['ideal_topup']
            )
            denominator = sum(
                products[product_id][i]['ideal_topup'] for product_id in products if
                products[product_id][i]['ideal_topup']
            )
            if denominator:
                month_value = self.percent_fn(
                    numerator,
                    denominator
                )
                if self.cell_value_less_than(month_value, 90):
                    style = 'color: red'
                elif self.cell_value_bigger_than(month_value, 100):
                    style = 'color: orange'
                else:
                    style = ''
                total_row.append({
                    'html': month_value,
                    'style': style,
                })
            else:
                total_row.append({
                    'html': 'pas de données',
                })
        return total_row

    @property
    def group_by(self):
        return ['real_date_repeat', 'product_id', 'product_name']

    @property
    def columns(self):
        columns = [
            DatabaseColumn("Date", SimpleColumn('real_date_repeat')),
            DatabaseColumn("Product ID", SimpleColumn('product_id')),
            DatabaseColumn("Product Name", SimpleColumn('product_name')),
            DatabaseColumn("Quantity of the product delivered", SumColumn('amt_delivered_convenience')),
            DatabaseColumn("Quantity of the product  suggested", SumColumn('ideal_topup')),
        ]
        return columns

    def get_product_satisfaction_rate_per_month(self, records):
        data = defaultdict(list)
        product_names = {}
        for record in records:
            if not self.date_in_selected_date_range(record['real_date_repeat']):
                continue
            if record['product_id'] not in data:
                for i in range(len(self.months)):
                    data[record['product_id']].append(defaultdict(int))
                product_names[record['product_id']] = record['product_name']
            month_index = self.get_index_of_month_in_selected_data_range(record['real_date_repeat'])
            if self.denominator_exists(record['ideal_topup']):
                if record['amt_delivered_convenience']:
                    data[record['product_id']][month_index]['amt_delivered_convenience'] += \
                        record['amt_delivered_convenience']['html']
                data[record['product_id']][month_index]['ideal_topup'] += record['ideal_topup']['html']
        return product_names, data

    def parse_satisfaction_rate_to_rows(self, product_names, data):
        rows = []
        for product_id in data:
            row = [product_names[product_id]]
            for i in range(len(self.months)):
                if data[product_id][i]['ideal_topup']:
                    month_value = self.percent_fn(
                        data[product_id][i]['amt_delivered_convenience'],
                        data[product_id][i]['ideal_topup']
                    )
                    if self.cell_value_less_than(month_value, 90):
                        style = 'color: red'
                    elif self.cell_value_bigger_than(month_value, 100):
                        style = 'color: orange'
                    else:
                        style = ''
                    row.append({
                        'html': month_value,
                        'style': style,
                    })
                else:
                    row.append({
                        'html': 'pas de données',
                        'style': '',
                    })
            rows.append(row)
        return rows

    @property
    def rows(self):
        records = self.get_data()
        product_names, data = self.get_product_satisfaction_rate_per_month(records)
        self.total_row = self.calculate_total_row(data)
        rows = self.parse_satisfaction_rate_to_rows(product_names, data)
        return sorted(rows, key=lambda x: x[0])

    @property
    def headers(self):
        headers = DataTablesHeader(DataTablesColumn('Produit'))
        for month in self.month_headers():
            headers.add_column(month)
        return headers


class ValuationOfPNAStockPerProductData(VisiteDeLOperateurPerProductDataSource):
    slug = 'valeur_des_stocks_pna_disponible_chaque_produit'
    comment = 'Valeur des stocks PNA disponible (chaque produit)'
    title = 'Valeur des stocks PNA disponible (chaque produit)'
    show_total = True
    custom_total_calculate = True

    def calculate_total_row(self, records):
        total_row = []
        data = defaultdict(int)
        for record in records:
            if not self.date_in_selected_date_range(record['real_date_repeat']):
                continue
            month_index = self.get_index_of_month_in_selected_data_range(record['real_date_repeat'])
            if record['final_pna_stock_valuation']:
                data[month_index] += record['final_pna_stock_valuation']['html']

        total_row.append('Total (CFA)')
        for month_index in range(len(self.months)):
            if data.get(month_index) is not None:
                total_row.append(
                    '{:,}'.format(data[month_index]).replace(',', '.')
                )
            else:
                total_row.append('pas de données')
        return total_row

    @property
    def group_by(self):
        return ['real_date_repeat', 'product_id', 'product_name']

    @property
    def columns(self):
        columns = [
            DatabaseColumn("Date", SimpleColumn('real_date_repeat')),
            DatabaseColumn("Product ID", SimpleColumn('product_id')),
            DatabaseColumn("Product Name", SimpleColumn('product_name')),
            DatabaseColumn("Products stock valuation", SumColumn('final_pna_stock_valuation')),
        ]
        return columns

    def get_product_valuation_of_pna_stock_per_month(self, records):
        data = defaultdict(list)
        product_names = {}
        for record in records:
            if not self.date_in_selected_date_range(record['real_date_repeat']):
                continue
            if record['final_pna_stock_valuation']:
                if record['product_id'] not in data:
                    for i in range(len(self.months)):
                        data[record['product_id']].append(defaultdict(int))
                    product_names[record['product_id']] = record['product_name']
                month_index = self.get_index_of_month_in_selected_data_range(record['real_date_repeat'])
                data[record['product_id']][month_index]['final_pna_stock_valuation'] += \
                    record['final_pna_stock_valuation']['html']
        return product_names, data

    @property
    def rows(self):
        records = self.get_data()
        product_names, data = self.get_product_valuation_of_pna_stock_per_month(records)

        rows = []
        for product_id in data:
            row = [product_names[product_id]]
            row.extend([
                '{:,}'.format(value['final_pna_stock_valuation']).replace(',', '.')
                if value.get('final_pna_stock_valuation') is not None
                else
                'pas de données'
                for value in data[product_id]
            ])
            rows.append(row)
        self.total_row = self.calculate_total_row(records)
        return sorted(rows, key=lambda x: x[0])

    @property
    def headers(self):
        headers = DataTablesHeader(DataTablesColumn('Produit'))
        for month in self.month_headers():
            headers.add_column(month)
        return headers


class LocationLevelMixin:
    config = {}

    @cached_property
    def selected_location(self):
        if self.config['location_id']:
            return SQLLocation.objects.get(location_id=self.config['location_id'])
        else:
            return None

    @cached_property
    def selected_location_type(self):
        if not self.selected_location:
            return 'national'
        return self.selected_location.location_type.code

    @cached_property
    def loc_type(self):
        if self.selected_location_type in ['national', 'region']:
            return 'region'
        elif self.selected_location_type == 'district':
            return 'district'
        else:
            return 'pps'

    @cached_property
    def loc_id(self):
        return "{}_id".format(self.loc_type)

    @cached_property
    def loc_name(self):
        return "{}_name".format(self.loc_type)

    @cached_property
    def loc_type_to_get(self):
        if self.selected_location_type == 'national':
            return 'region'
        elif self.selected_location_type == 'region':
            return 'district'
        else:
            return 'pps'

    @cached_property
    def loc_id_to_get(self):
        return "{}_id".format(self.loc_type_to_get)

    @cached_property
    def loc_name_to_get(self):
        return "{}_name".format(self.loc_type_to_get)


class ProductsAndProgramsMixin:
    config = {}

    @property
    @memoized
    def program_and_products(self):
        rows = {}
        all_data = ProductsInProgramWithNameData(config={'domain': self.config['domain']}).rows
        all_products_data = ProductData(config={'domain': self.config['domain']}).rows

        all_data = sorted(all_data, key=lambda x: x['program_name'])
        all_products_data = sorted(all_products_data, key=lambda x: x['product_name'])

        for data in all_data:
            program_name = data['program_name']
            program_id = data['program_id']
            product_ids = data['product_ids']
            length = len(product_ids)
            index = 0
            while index < length:
                product_id = product_ids[index]
                if product_id not in product_ids:
                    product_ids.pop(index)
                    index -= 1
                    length -= 1
                index += 1

            products_list = []
            for product_data in all_products_data:
                product_id = product_data['product_id']
                product_name = product_data['product_name']
                if product_id in product_ids:
                    products_list.append({
                        'product_id': product_id,
                        'product_name': product_name,
                    })

            rows[program_id] = [
                p['product_id'] for p in products_list
                if program_name if p['product_name'] is not None
            ]

        return rows

    def is_product_in_program(self, product_info, program):
        if product_info[0] in self.program_and_products[program] or \
                product_info[1] in self.program_and_products[program]:
            return True

        return False


class VisiteDeLOperateurPerProductV2DataSource(SqlData, LocationLevelMixin, ProductsAndProgramsMixin):
    slug = 'disponibilite'
    comment = 'Disponibilité de la gamme au niveau PPS : combien de PPS ont eu tous les produits disponibles'
    title = 'Disponibilité'

    def __init__(self, config):
        super(VisiteDeLOperateurPerProductV2DataSource, self).__init__()
        self.config = config

    @property
    def engine_id(self):
        return 'ucr'

    @property
    def table_name(self):
        config_domain = self.config['domain']
        doc_id = StaticDataSourceConfiguration.get_doc_id(config_domain, YEKSI_NAA_REPORTS_CONSUMPTION)
        config, _ = get_datasource_config(doc_id, config_domain)
        return get_table_name(config_domain, config.table_id)

    @property
    def filters(self):
        filters = [BETWEEN('real_date_precise', 'startdate', 'enddate')]
        if self.config['location_id']:
            filters.append(EQ(self.loc_id, 'location_id'))
        if self.config['product_product']:
            filters.append(EQ('product_id', 'product_product'))
        return filters

    @property
    def group_by(self):
        group_by = [
            self.loc_id_to_get, self.loc_name_to_get,
            'real_date_precise', 'product_is_outstock',
            'product_id', 'product_name', 'program_id',
        ]
        if self.loc_id_to_get != 'pps_id':
            group_by.append('pps_id')
            group_by.append('pps_name')

        return group_by

    @property
    def columns(self):
        columns = [
            DatabaseColumn('Date', SimpleColumn('real_date_precise')),
            DatabaseColumn('Location ID', SimpleColumn(self.loc_id_to_get)),
            DatabaseColumn('Location Name', SimpleColumn(self.loc_name_to_get)),
            DatabaseColumn('Product ID', SimpleColumn('product_id')),
            DatabaseColumn('Program ID', SimpleColumn('program_id')),
            DatabaseColumn('Product Name', SimpleColumn('product_name')),
            DatabaseColumn('Is product outstock', SimpleColumn('product_is_outstock')),
        ]
        if self.loc_id_to_get != 'pps_id':
            columns.append(DatabaseColumn('PPS ID', SimpleColumn('pps_id')))
            columns.append(DatabaseColumn('PPS Name', SimpleColumn('pps_name')))

        return columns

    @property
    def rows(self):
        rows_to_return = []
        rows = self.get_data()

        def clean_rows(data_to_clean):
            stocks = sorted(data_to_clean, key=lambda x: x['{}'.format(self.loc_name_to_get)])

            stocks_list = []
            added_locations = []
            added_programs = []
            added_products_for_locations = {}
            wanted_program = self.config.get('product_program', '')

            for stock in stocks:
                location_name = stock['{}'.format(self.loc_name_to_get)]
                location_id = stock['{}'.format(self.loc_id_to_get)]
                if location_id is None:
                    location_id = location_name
                product_name = stock['product_name']
                product_id = stock['product_id']
                program_id = stock['program_id'].split(' ')
                if len(program_id) > 1:
                    for program in program_id:
                        if self.is_product_in_program((product_id, product_name), program) and \
                                (program == wanted_program or not wanted_program):
                            stock['program_id'] = program
                            stocks.append(stock.copy())
                else:
                    data_dict = {
                        'location_name': location_name,
                        'location_id': location_id,
                        'program_id': program_id,
                        'products': []
                    }
                    if location_id in added_locations and program_id in added_programs:
                        amount_of_stocks = len(stocks_list)

                        location_position = 0
                        for r in range(0, amount_of_stocks):
                            current_location = stocks_list[r]['location_id']
                            if current_location == location_id:
                                location_position = r
                                break

                        added_products_for_location = \
                            [x['product_id'] for x in added_products_for_locations[location_id]]
                        products_for_location = added_products_for_locations[location_id]
                        if product_id not in added_products_for_location:
                            product_data = {
                                'product_name': product_name,
                                'product_id': product_id,
                                'in_ppses': 0,
                                'all_ppses': 0,
                            }
                            added_products_for_locations[location_id].append(product_data)
                            stocks_list[location_position]['products'].append(product_data)
                        amount_of_products_for_location = len(added_products_for_locations[location_id])

                        product_position = 0
                        for s in range(0, amount_of_products_for_location):
                            current_product = products_for_location[s]['product_id']
                            if current_product == product_id:
                                product_position = s
                                break

                        product_is_stock = True if stock['product_is_outstock'] == 0 else False
                        overall_position = stocks_list[location_position]['products'][product_position]
                        if product_is_stock:
                            overall_position['in_ppses'] += 1
                        overall_position['all_ppses'] += 1
                    else:
                        if isinstance(program_id, list):
                            program_id = program_id[0]
                        if location_id not in added_locations:
                            added_locations.append(location_id)
                        if program_id not in added_programs and \
                                (self.is_product_in_program((product_id, product_name), program_id) and
                                (program_id == wanted_program or not wanted_program)):
                            added_programs.append(program_id)
                        if program_id == wanted_program or not wanted_program:
                            product_data = {
                                'product_name': product_name,
                                'product_id': product_id,
                                'in_ppses': 0,
                                'all_ppses': 0,
                            }
                            product_is_stock = True if stock['product_is_outstock'] == 0 else False
                            if product_is_stock:
                                product_data['in_ppses'] += 1
                            product_data['all_ppses'] += 1
                            data_dict['products'].append(product_data)
                            stocks_list.append(data_dict)
                            added_products_for_locations[location_id] = [product_data]

            stocks_list_to_return = sorted(stocks_list, key=lambda x: x['location_id'])

            return stocks_list_to_return

        fresh_records_dict = {}
        for row in rows:
            pps_id = row['pps_id']
            product_id = row['product_id']
            if pps_id not in fresh_records_dict.keys():
                fresh_records_dict[pps_id] = {
                    product_id: row
                }
            else:
                if product_id not in fresh_records_dict[pps_id].keys():
                    fresh_records_dict[pps_id][product_id] = row
                else:
                    date = fresh_records_dict[pps_id][product_id]['real_date_precise']
                    new_date = row['real_date_precise']
                    if new_date > date:
                        fresh_records_dict[pps_id][product_id] = row

        for pps_id, products in fresh_records_dict.items():
            for product, product_data in products.items():
                rows_to_return.append(product_data)

        clean_data = clean_rows(rows_to_return)

        return clean_data


class TauxDeRuptureRateData(SqlData, LocationLevelMixin, ProductsAndProgramsMixin):
    slug = 'taux_de_rupture_par_pps'
    comment = 'Nombre de produits en rupture sur le nombre total de produits du PPS'
    title = 'Taux de Rupture par PPS'
    show_total = True
    custom_total_calculate = True

    def __init__(self, config):
        super(TauxDeRuptureRateData, self).__init__()
        self.config = config

    @property
    def engine_id(self):
        return 'ucr'

    @property
    def table_name(self):
        config_domain = self.config['domain']
        doc_id = StaticDataSourceConfiguration.get_doc_id(config_domain, YEKSI_NAA_REPORTS_CONSUMPTION)
        config, _ = get_datasource_config(doc_id, config_domain)
        return get_table_name(config_domain, config.table_id)

    @property
    def filters(self):
        filters = [BETWEEN('real_date_precise', 'startdate', 'enddate')]
        if self.config['location_id']:
            filters.append(EQ(self.loc_id, 'location_id'))
        if self.config['product_product']:
            filters.append(EQ('product_id', 'product_product'))
        return filters

    @property
    def group_by(self):
        group_by = [
            self.loc_id_to_get, self.loc_name_to_get,
            'real_date_precise', 'product_is_outstock',
            'product_id', 'product_name', 'program_id'
        ]
        if self.loc_id_to_get != 'pps_id':
            group_by.append('pps_id')
            group_by.append('pps_name')

        return group_by

    @property
    def columns(self):
        columns = [
            DatabaseColumn('Date', SimpleColumn('real_date_precise')),
            DatabaseColumn('Location ID', SimpleColumn(self.loc_id_to_get)),
            DatabaseColumn('Location Name', SimpleColumn(self.loc_name_to_get)),
            DatabaseColumn('Product ID', SimpleColumn('product_id')),
            DatabaseColumn('Program ID', SimpleColumn('program_id')),
            DatabaseColumn('Product Name', SimpleColumn('product_name')),
            DatabaseColumn('Is product outstock', SimpleColumn('product_is_outstock')),
        ]
        if self.loc_id_to_get != 'pps_id':
            columns.append(DatabaseColumn('PPS ID', SimpleColumn('pps_id')))
            columns.append(DatabaseColumn('PPS Name', SimpleColumn('pps_name')))

        return columns

    @property
    def rows(self):
        rows_to_return = []
        rows = self.get_data()

        def clean_rows(data_to_clean):
            stocks = sorted(data_to_clean, key=lambda x: x['{}'.format(self.loc_name_to_get)])

            stocks_list = []
            added_locations = []
            added_programs = []
            added_products_for_locations = {}
            wanted_program = self.config.get('product_program', '')

            for stock in stocks:
                location_name = stock['{}'.format(self.loc_name_to_get)]
                location_id = stock['{}'.format(self.loc_id_to_get)]
                if location_id is None:
                    location_id = location_name
                product_name = stock['product_name']
                product_id = stock['product_id']
                program_id = stock['program_id'].split(' ')
                if len(program_id) > 1:
                    for program in program_id:
                        if self.is_product_in_program((product_id, product_name), program) and \
                                (program == wanted_program or not wanted_program):
                            stock['program_id'] = program
                            stocks.append(stock.copy())
                else:
                    data_dict = {
                        'location_name': location_name,
                        'location_id': location_id,
                        'program_id': wanted_program if wanted_program else '',
                        'products': []
                    }
                    if location_id in added_locations and program_id in added_programs:
                        amount_of_stocks = len(stocks_list)

                        location_position = 0
                        for r in range(0, amount_of_stocks):
                            current_location = stocks_list[r]['location_id']
                            if current_location == location_id:
                                location_position = r
                                break

                        added_products_for_location = \
                            [x['product_id'] for x in added_products_for_locations[location_id]]
                        products_for_location = added_products_for_locations[location_id]
                        if product_id not in added_products_for_location:
                            product_data = {
                                'product_name': product_name,
                                'product_id': product_id,
                                'out_in_ppses': 0,
                                'all_ppses': 0,
                            }
                            added_products_for_locations[location_id].append(product_data)
                            stocks_list[location_position]['products'].append(product_data)
                        amount_of_products_for_location = len(added_products_for_locations[location_id])

                        product_position = 0
                        for s in range(0, amount_of_products_for_location):
                            current_product = products_for_location[s]['product_id']
                            if current_product == product_id:
                                product_position = s
                                break

                        product_is_outstock = True if stock['product_is_outstock'] == 1 else False
                        overall_position = stocks_list[location_position]['products'][product_position]
                        if product_is_outstock:
                            overall_position['out_in_ppses'] += 1
                        overall_position['all_ppses'] += 1
                    else:
                        if isinstance(program_id, list):
                            program_id = program_id[0]
                        if location_id not in added_locations:
                            added_locations.append(location_id)
                        if program_id not in added_programs and \
                                (self.is_product_in_program((product_id, product_name), program_id) and
                                (program_id == wanted_program or not wanted_program)):
                            added_programs.append(program_id)
                        if program_id == wanted_program or not wanted_program:
                            product_data = {
                                'product_name': product_name,
                                'product_id': product_id,
                                'out_in_ppses': 0,
                                'all_ppses': 0,
                            }
                            product_is_outstock = True if stock['product_is_outstock'] == 1 else False
                            if product_is_outstock:
                                product_data['out_in_ppses'] += 1
                            product_data['all_ppses'] += 1
                            data_dict['products'].append(product_data)
                            stocks_list.append(data_dict)
                            added_products_for_locations[location_id] = [product_data]

            stocks_list_to_return = sorted(stocks_list, key=lambda x: x['location_id'])

            return stocks_list_to_return

        fresh_records_dict = {}
        for row in rows:
            pps_id = row['pps_id']
            product_id = row['product_id']
            if pps_id not in fresh_records_dict.keys():
                fresh_records_dict[pps_id] = {
                    product_id: row
                }
            else:
                if product_id not in fresh_records_dict[pps_id].keys():
                    fresh_records_dict[pps_id][product_id] = row
                else:
                    date = fresh_records_dict[pps_id][product_id]['real_date_precise']
                    new_date = row['real_date_precise']
                    if new_date > date:
                        fresh_records_dict[pps_id][product_id] = row

        for pps_id, products in fresh_records_dict.items():
            for product, product_data in products.items():
                rows_to_return.append(product_data)

        clean_data = clean_rows(rows_to_return)

        return clean_data


class ConsommationPerProductData(SqlData, LocationLevelMixin, ProductsAndProgramsMixin):
    slug = 'consommation_per_product'
    comment = ''
    title = 'Consommation per product'
    show_total = True
    custom_total_calculate = True

    def __init__(self, config):
        super(ConsommationPerProductData, self).__init__()
        self.config = config

    @property
    def engine_id(self):
        return 'ucr'

    @property
    def table_name(self):
        config_domain = self.config['domain']
        doc_id = StaticDataSourceConfiguration.get_doc_id(config_domain, YEKSI_NAA_REPORTS_CONSUMPTION)
        config, _ = get_datasource_config(doc_id, config_domain)
        return get_table_name(config_domain, config.table_id)

    @property
    def filters(self):
        filters = [BETWEEN('real_date_precise', 'startdate', 'enddate')]
        if self.config['location_id']:
            filters.append(EQ(self.loc_id, 'location_id'))
        if self.config['product_product']:
            filters.append(EQ('product_id', 'product_product'))
        return filters

    @property
    def group_by(self):
        group_by = [
            self.loc_id_to_get, self.loc_name_to_get,
            'real_date_precise', 'actual_consumption',
            'product_id', 'product_name', 'program_id'
        ]
        if self.loc_id_to_get != 'pps_id':
            group_by.append('pps_id')
            group_by.append('pps_name')

        return group_by

    @property
    def columns(self):
        columns = [
            DatabaseColumn('Date', SimpleColumn('real_date_precise')),
            DatabaseColumn('Location ID', SimpleColumn(self.loc_id_to_get)),
            DatabaseColumn('Location Name', SimpleColumn(self.loc_name_to_get)),
            DatabaseColumn("Program ID", SimpleColumn('program_id')),
            DatabaseColumn("Product ID", SimpleColumn('product_id')),
            DatabaseColumn("Product name", SimpleColumn('product_name')),
            DatabaseColumn("Consumption", SimpleColumn('actual_consumption'))
        ]
        if self.loc_id_to_get != 'pps_id':
            columns.append(DatabaseColumn('PPS ID', SimpleColumn('pps_id')))
            columns.append(DatabaseColumn('PPS Name', SimpleColumn('pps_name')))

        return columns

    @property
    def rows(self):
        rows = self.get_data()

        def clean_rows(data_to_clean):
            consumptions = sorted(data_to_clean, key=lambda x: x['{}'.format(self.loc_name_to_get)])

            consumptions_list = []
            added_locations = []
            added_programs = []
            added_products_for_locations = {}
            wanted_program = self.config.get('product_program', '')

            for consumption in consumptions:
                location_name = consumption['{}'.format(self.loc_name_to_get)]
                location_id = consumption['{}'.format(self.loc_id_to_get)]
                if location_id is None:
                    location_id = location_name
                product_name = consumption['product_name']
                product_id = consumption['product_id']
                program_id = consumption['program_id'].split(' ')
                actual_consumption = consumption['actual_consumption']
                if len(program_id) > 1:
                    for program in program_id:
                        if self.is_product_in_program((product_id, product_name), program) and \
                                (program == wanted_program or not wanted_program):
                            consumption['program_id'] = program
                            consumptions.append(consumption.copy())
                else:
                    data_dict = {
                        'location_name': location_name,
                        'location_id': location_id,
                        'program_id': program_id,
                        'products': []
                    }
                    if location_id in added_locations and program_id in added_programs:
                        amount_of_stocks = len(consumptions_list)

                        location_position = 0
                        for r in range(0, amount_of_stocks):
                            current_location = consumptions_list[r]['location_id']
                            if current_location == location_id:
                                location_position = r
                                break

                        products = consumptions_list[location_position]['products']
                        product_names = [x['product_name'] for x in products]
                        if product_name in product_names:
                            for product in products:
                                if product['product_name'] == product_name:
                                    product['actual_consumption'] += actual_consumption
                        else:
                            products.append({
                                'product_name': product_name,
                                'product_id': product_id,
                                'actual_consumption': actual_consumption
                            })
                    else:
                        if isinstance(program_id, list):
                            program_id = program_id[0]
                        if location_id not in added_locations:
                            added_locations.append(location_id)
                        if program_id not in added_programs and \
                                (self.is_product_in_program((product_id, product_name), program_id) and
                                (program_id == wanted_program or not wanted_program)):
                            added_programs.append(program_id)
                        if program_id == wanted_program or not wanted_program:
                            product_data = {
                                'product_name': product_name,
                                'product_id': product_id,
                                'actual_consumption': 0,
                            }
                            product_data['actual_consumption'] += actual_consumption
                            data_dict['products'].append(product_data)
                            consumptions_list.append(data_dict)
                            added_products_for_locations[location_id] = [product_data]

            consumptions_list_to_return = sorted(consumptions_list, key=lambda x: x['location_id'])

            return consumptions_list_to_return

        clean_data = clean_rows(rows)

        return clean_data


class LossRatePerProductData2(VisiteDeLOperateurPerProductDataSource):
    slug = 'taux_de_perte'
    comment = 'Taux de Perte (hors péremption)'
    title = 'Taux de Perte (hors péremption)'
    show_total = True
    custom_total_calculate = True

    def calculate_total_row(self, data):
        if 'region_id' in self.config and self.config['region_id']:
            total_row = [{
                'html': 'Taux par Région',
            }]
        elif 'district_id' in self.config and self.config['district_id']:
            total_row = [{
                'html': 'Taux par District',
            }]
        elif 'pps_id' in self.config and self.config['pps_id']:
            total_row = [{
                'html': '',
            }]
        else:
            total_row = [{
                'html': 'Taux par Pays',
            }]
        total_numerator = 0
        total_denominator = 0
        for i in range(len(self.products)):
            numerator = sum(
                data[loc_id][i]['loss_amt'] for loc_id in data if
                data[loc_id][i]['final_pna_stock']
            )
            denominator = sum(
                data[loc_id][i]['final_pna_stock'] for loc_id in data if
                data[loc_id][i]['final_pna_stock']
            )
            total_numerator += numerator
            total_denominator += denominator
            total_value = self.percent_fn(
                numerator,
                denominator
            )
            if denominator:
                total_row.append({
                    'html': total_value,
                })
            else:
                total_row.append({
                    'html': 'pas de données',
                })
        total_value = self.percent_fn(
            total_numerator,
            total_denominator
        )
        if total_denominator:
            total_row.append({
                'html': total_value,
            })
        else:
            total_row.append({
                'html': 'pas de données',
            })
        return total_row

    @property
    def group_by(self):
        return ['real_date_repeat', self.loc_id, self.loc_name, 'product_id', 'product_name']

    @cached_property
    def loc_id(self):
        if 'pps_id' in self.config or 'district_id' in self.config:
            return 'pps_id'
        elif 'region_id' in self.config:
            return 'district_id'
        else:
            return 'region_id'

    @cached_property
    def loc_name(self):
        if 'pps_id' in self.config or 'district_id' in self.config:
            return 'pps_name'
        elif 'region_id' in self.config:
            return 'district_name'
        else:
            return 'region_name'

    @property
    def columns(self):
        columns = [
            DatabaseColumn("Date", SimpleColumn('real_date_repeat')),
            DatabaseColumn("Product ID", SimpleColumn('product_id')),
            DatabaseColumn("Product Name", SimpleColumn('product_name')),
            DatabaseColumn("Total number of PNA lost product", SumColumn('loss_amt')),
            DatabaseColumn("PNA final stock", SumColumn('final_pna_stock')),
        ]
        if self.loc_id == 'pps_id':
            columns.append(DatabaseColumn("PPS ID", SimpleColumn('pps_id')))
            columns.append(DatabaseColumn("PPS Name", SimpleColumn('pps_name')))
        elif self.loc_id == 'district_id':
            columns.append(DatabaseColumn("District ID", SimpleColumn('district_id')))
            columns.append(DatabaseColumn("District Name", SimpleColumn('district_name')))
        else:
            columns.append(DatabaseColumn("Region ID", SimpleColumn('region_id')))
            columns.append(DatabaseColumn("Region Name", SimpleColumn('region_name')))
        return columns

    def get_average_loss_rate_in_location(self, data_per_localization):
        numerator = 0
        denominator = 0
        for data_in_month in data_per_localization:
            if data_in_month and data_in_month['final_pna_stock']:
                numerator += data_in_month['loss_amt']
                denominator += data_in_month['final_pna_stock']
        if denominator:
            value = self.percent_fn(
                numerator,
                denominator,
            )
            return {
                'html': value,
            }
        else:
            return {
                'html': 'pas de données',
            }

    def parse_loss_rate_to_rows(self, loc_names, data):
        rows = []
        for loc_id in data:
            row = [{
                'html': loc_names[loc_id],
            }]
            for i in range(len(self.products)):
                if data[loc_id][i]['final_pna_stock']:
                    product_value = self.percent_fn(
                        data[loc_id][i]['loss_amt'],
                        data[loc_id][i]['final_pna_stock']
                    )
                    row.append({
                        'html': product_value,
                    })
                else:
                    row.append({
                        'html': 'pas de données',
                    })
            row.append(self.get_average_loss_rate_in_location(data[loc_id]))
            rows.append(row)
        return rows

    def get_loss_rate_per_month(self, records):
        data = defaultdict(list)
        loc_names = {}

        for record in records:
            if record[self.loc_id] not in data:
                for i in range(len(self.products)):
                    data[record[self.loc_id]].append(defaultdict(int))
                loc_names[record[self.loc_id]] = record[self.loc_name]

            if not self.date_in_selected_date_range(record['real_date_repeat']) \
                    or record['product_id'] not in self.products:
                continue

            product = self.products.index(record['product_id'])

            if self.denominator_exists(record['final_pna_stock']):
                if record['loss_amt']:
                    data[record[self.loc_id]][product]['loss_amt'] += record['loss_amt']['html']
                data[record[self.loc_id]][product]['final_pna_stock'] += record['final_pna_stock']['html']

        return loc_names, data

    def flatten_records_by_date(self, records):
        flatten_records = {}
        for record in records:
            if not self.date_in_selected_date_range(record['real_date_repeat']) \
                    or record['product_id'] not in self.products:
                continue

            if record[self.loc_id]:
                location = (record[self.loc_id]) + record['product_id']
            else:
                continue
            final_stock = record['final_pna_stock']
            loss_amt = record['loss_amt']
            if not flatten_records.get(location):
                flatten_records[location] = record
                if not loss_amt:
                    flatten_records[location]['loss_amt'] = {'html': 0}
                if not final_stock:
                    flatten_records[location]['final_pna_stock'] = {'html': 0}
            else:
                if final_stock:
                    flatten_records[location]['final_pna_stock']['html'] += final_stock['html']
                if loss_amt:
                    flatten_records[location]['loss_amt']['html'] += loss_amt['html']

        return flatten_records.values()

    def rows(self, for_chart=False):
        records = self.get_data()
        records = self.flatten_records_by_date(records)

        if not for_chart:
            loc_names, data = self.get_loss_rate_per_month(records)
            self.total_row = self.calculate_total_row(data)
            rows = self.parse_loss_rate_to_rows(loc_names, data)
            return sorted(rows, key=lambda x: x[0]['html'])
        else:
            rows = self._get_data_for_products(records)
            return sorted(rows, key=lambda x: x), rows

    def _get_data_for_products(self, records):
        products = {}
        added_products = []
        for record in records:
            product_id = record['product_id']
            product_name = record['product_name']
            loss_amt = record['loss_amt']['html']
            final_pna_stock = record['final_pna_stock']['html']
            if product_id not in added_products and final_pna_stock != 0:
                added_products.append(product_id)
                products[product_name] = {
                    'loss_amt': loss_amt,
                    'final_pna_stock': final_pna_stock,
                    'percent': self.percent_fn(loss_amt, final_pna_stock)
                }
            elif product_id in added_products and final_pna_stock != 0:
                products[product_name]['loss_amt'] += loss_amt
                products[product_name]['final_pna_stock'] += final_pna_stock
                products[product_name]['percent'] = self.percent_fn(
                    products[product_name]['loss_amt'], products[product_name]['final_pna_stock']
                )

        return products

    @property
    def headers(self):
        if self.loc_id == 'pps_id':
            first_row = 'PPS'
        elif self.loc_id == 'district_id':
            first_row = 'District'
        else:
            first_row = 'Région'

        product_names = dict((product_id, "") for product_id in self.products)
        for row in self.get_data():
            id = row['product_id']

            if product_names.get(id, None) == "":
                product_names[id] = row['product_name']

        headers = DataTablesHeader(DataTablesColumn(first_row))
        pn = [name for name in product_names.values() if name]
        pn.sort()
        for product in pn:
            headers.add_column(DataTablesColumn(product))
        headers.add_column(DataTablesColumn('SYNTHESE'))

        return headers

    @property
    def all_unsorted_products(self):
        products = [self.config['product_product']]
        if not self.config['product_product']:
            selected_program = self.config['product_program']
            program = ProductsInProgramData(config=dict(domain=self.config['domain'])).rows
            products = []
            for p in program:
                if selected_program and p[0] != selected_program:
                    continue
                products.extend(p[1].split(' '))
            products.sort()

        products = list(set(products))
        products.sort()
        return products

    @property
    @memoized
    def products(self):
        product_names = dict((product_id, "") for product_id in self.all_unsorted_products)
        for row in self.get_data():
            id = row['product_id']
            if product_names.get(id, None) == "":
                product_names[id] = row['product_name']

        pn = [key[0] for key in sorted(product_names.items(), key=lambda x: x[1]) if key[1]]
        return pn


class ExpirationRatePerProductData2(LossRatePerProductData2):
    slug = 'taux_de_peremption'
    comment = 'valeur péremption sur valeur totale'
    title = 'Taux de Péremption'
    show_total = True
    custom_total_calculate = True

    def calculate_total_row(self, data):
        if 'region_id' in self.config and self.config['region_id']:
            total_row = [{
                'html': 'Taux par Région',
            }]
        elif 'district_id' in self.config and self.config['district_id']:
            total_row = [{
                'html': 'Taux par District',
            }]
        elif 'pps_id' in self.config and self.config['pps_id']:
            total_row = [{
                'html': '',
            }]
        else:
            total_row = [{
                'html': 'Taux par Pays',
            }]
        total_numerator = 0
        total_denominator = 0
        for i in range(len(self.products)):
            numerator = sum(
                data[loc_id][i]['expired_pna_valuation'] for loc_id in data if
                data[loc_id][i]['final_pna_stock_valuation']
            )
            denominator = sum(
                data[loc_id][i]['final_pna_stock_valuation'] for loc_id in data if
                data[loc_id][i]['final_pna_stock_valuation']
            )
            total_numerator += numerator
            total_denominator += denominator
            total_value = self.percent_fn(
                numerator,
                denominator
            )
            if denominator:
                total_row.append({
                    'html': total_value,
                    'style': 'color: red' if self.cell_value_bigger_than(total_value, 5) else '',
                })
            else:
                total_row.append({
                    'html': 'pas de données',
                })
        total_value = self.percent_fn(
            total_numerator,
            total_denominator
        )
        if total_denominator:
            total_row.append({
                'html': total_value,
                'style': 'color: red' if self.cell_value_bigger_than(total_value, 5) else '',
            })
        else:
            total_row.append({
                'html': 'pas de données',
            })
        return total_row

    @property
    def columns(self):
        columns = super(ExpirationRatePerProductData2, self).columns
        columns.extend([
            DatabaseColumn("Expired products valuation", SumColumn('expired_pna_valuation')),
            DatabaseColumn("Products stock valuation", SumColumn('final_pna_stock_valuation'))
        ])
        return columns

    def get_average_expiration_rate_in_location(self, data_per_localization):
        numerator = 0
        denominator = 0
        for data_in_month in data_per_localization:
            if data_in_month and data_in_month['final_pna_stock_valuation']:
                numerator += data_in_month['expired_pna_valuation']
                denominator += data_in_month['final_pna_stock_valuation']
        if denominator:
            value = self.percent_fn(
                numerator,
                denominator,
            )
            return {
                'html': value,
                'style': 'color: red' if self.cell_value_bigger_than(value, 5) else '',
            }
        else:
            return {
                'html': 'pas de données',
            }

    def parse_expiration_rate_to_rows(self, loc_names, data):
        rows = []
        for loc_id in data:
            row = [{
                'html': loc_names[loc_id],
            }]
            for i in range(len(self.products)):
                if data[loc_id][i]['final_pna_stock_valuation']:
                    product_value = self.percent_fn(
                        data[loc_id][i]['expired_pna_valuation'],
                        data[loc_id][i]['final_pna_stock_valuation']
                    )
                    row.append({
                        'html': product_value,
                    })
                else:
                    row.append({
                        'html': 'pas de données',
                    })
            row.append(self.get_average_expiration_rate_in_location(data[loc_id]))
            rows.append(row)
        return rows

    def get_expiration_rate_per_month(self, records):
        data = defaultdict(list)
        loc_names = {}
        for record in records:
            if record[self.loc_id] not in data:
                for i in range(len(self.products)):
                    data[record[self.loc_id]].append(defaultdict(int))
                loc_names[record[self.loc_id]] = record[self.loc_name]

            if not self.date_in_selected_date_range(record['real_date_repeat']) \
                    or record['product_id'] not in self.products:
                continue

            product = self.products.index(record['product_id'])
            if self.denominator_exists(record['final_pna_stock_valuation']):
                if record['expired_pna_valuation']:
                    data[record[self.loc_id]][product]['expired_pna_valuation'] += \
                        record['expired_pna_valuation']['html']
                data[record[self.loc_id]][product]['final_pna_stock_valuation'] += \
                    record['final_pna_stock_valuation']['html']
        return loc_names, data

    def rows(self, for_chart=False):
        records = self.get_data()

        if not for_chart:
            loc_names, data = self.get_expiration_rate_per_month(records)
            self.total_row = self.calculate_total_row(data)
            rows = self.parse_expiration_rate_to_rows(loc_names, data)
            return sorted(rows, key=lambda x: x[0]['html'])
        else:
            rows = self._get_data_for_products(records)
            return sorted(rows, key=lambda x: x), rows

    def _get_data_for_products(self, records):
        products = {}
        added_products = []
        for record in records:
            product_id = record['product_id']
            product_name = record['product_name']
            expired_pna_valuation = record['expired_pna_valuation']['html']
            final_pna_stock_valuation = record['final_pna_stock_valuation']['html']
            if product_id not in added_products and product_id in self.products and final_pna_stock_valuation != 0:
                added_products.append(product_id)
                products[product_name] = {
                    'expired_pna_valuation': expired_pna_valuation,
                    'final_pna_stock_valuation': final_pna_stock_valuation,
                    'percent': self.percent_fn(expired_pna_valuation, final_pna_stock_valuation)
                }
            elif product_id in added_products and final_pna_stock_valuation != 0:
                products[product_name]['expired_pna_valuation'] += expired_pna_valuation
                products[product_name]['final_pna_stock_valuation'] += final_pna_stock_valuation
                products[product_name]['percent'] = self.percent_fn(
                    products[product_name]['expired_pna_valuation'],
                    products[product_name]['final_pna_stock_valuation']
                )

        return products


class SatisfactionRateAfterDeliveryPerProductData(LocationLevelMixin, VisiteDeLOperateurPerProductDataSource):
    slug = 'taux_de_satisfaction_report'
    comment = 'produits proposés sur produits livrés'
    title = 'Taux de satisfaction (après livraison)'
    show_total = True
    custom_total_calculate = True

    @property
    def filters(self):
        filters = [BETWEEN('real_date_repeat', 'startdate', 'enddate')]
        if self.config['location_id']:
            filters.append(EQ(self.loc_id, 'location_id'))
        if self.config['product_product']:
            filters.append(EQ('product_id', 'product_product'))
        return filters

    @property
    def group_by(self):
        group_by = [
            self.loc_id_to_get, self.loc_name_to_get,
            'real_date_repeat', 'select_programs',
            'product_id', 'product_name', 'ideal_topup',
            'amt_delivered_convenience'
        ]
        if self.loc_id_to_get != 'pps_id':
            group_by.append('pps_id')
            group_by.append('pps_name')

        return group_by

    @property
    def columns(self):
        columns = [
            DatabaseColumn("Date", SimpleColumn('real_date_repeat')),
            DatabaseColumn('Location ID', SimpleColumn(self.loc_id_to_get)),
            DatabaseColumn('Location Name', SimpleColumn(self.loc_name_to_get)),
            DatabaseColumn("Product ID", SimpleColumn('product_id')),
            DatabaseColumn("Product Name", SimpleColumn('product_name')),
            DatabaseColumn("Programs", SimpleColumn('select_programs')),
            DatabaseColumn("Quantity of the product delivered", SumColumn('amt_delivered_convenience')),
            DatabaseColumn("Quantity of the product suggested", SumColumn('ideal_topup')),
        ]
        if self.loc_id_to_get != 'pps_id':
            columns.append(DatabaseColumn('PPS ID', SimpleColumn('pps_id')))
            columns.append(DatabaseColumn('PPS Name', SimpleColumn('pps_name')))

        return columns

    @property
    @memoized
    def program_and_products(self):
        rows = {}
        all_data = ProductsInProgramWithNameData(config={'domain': self.config['domain']}).rows
        all_products_data = ProductData(config={'domain': self.config['domain']}).rows

        all_data = sorted(all_data, key=lambda x: x['program_name'])
        all_products_data = sorted(all_products_data, key=lambda x: x['product_name'])

        for data in all_data:
            program_name = data['program_name']
            program_id = data['program_id']
            product_ids = data['product_ids']
            length = len(product_ids)
            index = 0
            while index < length:
                product_id = product_ids[index]
                if product_id not in product_ids:
                    product_ids.pop(index)
                    index -= 1
                    length -= 1
                index += 1

            products_list = []
            for product_data in all_products_data:
                product_id = product_data['product_id']
                product_name = product_data['product_name']
                if product_id in product_ids:
                    products_list.append({
                        'product_id': product_id,
                        'product_name': product_name,
                    })

            rows[program_id] = [
                p['product_id'] for p in products_list
                if program_name if p['product_name'] is not None
            ]

        return rows

    @property
    def rows(self):
        rows = self.get_data()

        def clean_rows(data_to_clean):
            quantities = sorted(data_to_clean, key=lambda x: x['{}'.format(self.loc_name_to_get)])
            quantities_list = []
            added_locations = []
            added_programs = []
            added_products_for_locations = {}
            wanted_program = self.config.get('product_program', '')

            for quantity in quantities:
                location_id = quantity['{}'.format(self.loc_id_to_get)]
                location_name = quantity['{}'.format(self.loc_name_to_get)]
                if location_id is None:
                    location_id = location_name
                product_name = quantity['product_name']
                product_id = quantity['product_id']
                program_id = quantity['select_programs'].split(' ')
                amt_delivered_convenience = quantity['amt_delivered_convenience']['sort_key']
                ideal_topup = quantity['ideal_topup']['sort_key']
                if len(program_id) > 1:
                    for program in program_id:
                        if (program == wanted_program and product_id in self.program_and_products[program]) \
                                or not wanted_program:
                            quantity['select_programs'] = program
                            quantities.append(quantity.copy())
                else:
                    data_dict = {
                        'location_name': location_name,
                        'location_id': location_id,
                        'program_id': program_id,
                        'products': []
                    }
                    if location_id in added_locations and program_id in added_programs:
                        amount_of_stocks = len(quantities_list)

                        location_position = 0
                        for r in range(0, amount_of_stocks):
                            current_location = quantities_list[r]['location_id']
                            if current_location == location_id:
                                location_position = r
                                break

                        added_products_for_location = \
                            [x['product_id'] for x in added_products_for_locations[location_id]]
                        products_for_location = added_products_for_locations[location_id]
                        if product_id not in added_products_for_location:
                            product_data = {
                                'product_name': product_name,
                                'product_id': product_id,
                                'amt_delivered_convenience': 0,
                                'ideal_topup': 0,
                            }
                            added_products_for_locations[location_id].append(product_data)
                            quantities_list[location_position]['products'].append(product_data)

                        amount_of_products_for_location = len(added_products_for_locations[location_id])
                        product_position = 0
                        for s in range(0, amount_of_products_for_location):
                            current_product = products_for_location[s]['product_id']
                            if current_product == product_id:
                                product_position = s
                                break
                        overall_position = quantities_list[location_position]['products'][product_position]
                        overall_position['amt_delivered_convenience'] += amt_delivered_convenience
                        overall_position['ideal_topup'] += ideal_topup
                    else:
                        if isinstance(program_id, list):
                            program_id = program_id[0]
                        if location_id not in added_locations:
                            added_locations.append(location_id)
                        if program_id not in added_programs and \
                            ((program_id == wanted_program and product_id in self.program_and_products[program_id])
                                or not wanted_program):
                            added_programs.append(program_id)
                        if program_id == wanted_program or not wanted_program:
                            product_data = {
                                'product_name': product_name,
                                'product_id': product_id,
                                'amt_delivered_convenience': 0,
                                'ideal_topup': 0,
                            }
                            product_data['amt_delivered_convenience'] += amt_delivered_convenience
                            product_data['ideal_topup'] += ideal_topup
                            data_dict['products'].append(product_data)
                            quantities_list.append(data_dict)
                            added_products_for_locations[location_id] = [product_data]

            quantities_list_to_return = sorted(quantities_list, key=lambda x: x['location_id'])

            return quantities_list_to_return

        clean_data = clean_rows(rows)

        return clean_data


class ValuationOfPNAStockPerProductV2Data(LocationLevelMixin, VisiteDeLOperateurPerProductDataSource):
    slug = 'valeur_des_stocks_pna_disponible_chaque_produit'
    comment = 'Valeur des stocks PNA disponible (chaque produit)'
    title = 'Valeur des stocks PNA disponible (chaque produit)'
    show_total = True
    custom_total_calculate = True

    def __init__(self, config):
        super(ValuationOfPNAStockPerProductV2Data, self).__init__()
        self.config = config

    @property
    def engine_id(self):
        return 'ucr'

    @property
    def table_name(self):
        config_domain = self.config['domain']
        doc_id = StaticDataSourceConfiguration.get_doc_id(
            config_domain,
            YEKSI_NAA_REPORTS_VISITE_DE_L_OPERATOUR_PER_PRODUCT
        )
        config, _ = get_datasource_config(doc_id, config_domain)
        return get_table_name(config_domain, config.table_id)

    @property
    def group_by(self):
        group_by = [
            'real_date_repeat', 'product_id', 'product_name', 'select_programs',
            self.loc_id_to_get, self.loc_name_to_get,
            'final_pna_stock_valuation'
        ]
        if self.loc_id_to_get != 'pps_id':
            group_by.append('pps_id')
            group_by.append('pps_name')

        return group_by

    @property
    def columns(self):
        columns = [
            DatabaseColumn('Location ID', SimpleColumn(self.loc_id_to_get)),
            DatabaseColumn('Location Name', SimpleColumn(self.loc_name_to_get)),
            DatabaseColumn("Date", SimpleColumn('real_date_repeat')),
            DatabaseColumn("Product ID", SimpleColumn('product_id')),
            DatabaseColumn("Product Name", SimpleColumn('product_name')),
            DatabaseColumn("Programs", SimpleColumn('select_programs')),
            DatabaseColumn("Products stock valuation", SumColumn('final_pna_stock_valuation')),
        ]
        if self.loc_id_to_get != 'pps_id':
            columns.append(DatabaseColumn('PPS ID', SimpleColumn('pps_id')))
            columns.append(DatabaseColumn('PPS Name', SimpleColumn('pps_name')))

        return columns

    @property
    def filters(self):
        filters = [BETWEEN('real_date_repeat', 'startdate', 'enddate')]
        if self.config['location_id']:
            filters.append(EQ(self.loc_id, 'location_id'))
        if self.config['product_product']:
            filters.append(EQ('product_id', 'product_product'))
        return filters

    @property
    @memoized
    def program_and_products(self):
        rows = {}
        all_data = ProductsInProgramWithNameData(config={'domain': self.config['domain']}).rows
        all_products_data = ProductData(config={'domain': self.config['domain']}).rows

        all_data = sorted(all_data, key=lambda x: x['program_name'])
        all_products_data = sorted(all_products_data, key=lambda x: x['product_name'])

        for data in all_data:
            program_name = data['program_name']
            program_id = data['program_id']
            product_ids = data['product_ids']
            length = len(product_ids)
            index = 0
            while index < length:
                product_id = product_ids[index]
                if product_id not in product_ids:
                    product_ids.pop(index)
                    index -= 1
                    length -= 1
                index += 1

            products_list = []
            for product_data in all_products_data:
                product_id = product_data['product_id']
                product_name = product_data['product_name']
                if product_id in product_ids:
                    products_list.append({
                        'product_id': product_id,
                        'product_name': product_name,
                    })

            rows[program_id] = [
                p['product_id'] for p in products_list
                if program_name if p['product_name'] is not None
            ]

        return rows

    @property
    def rows(self):
        rows = self.get_data()

        def clean_rows(data_to_clean):
            pnas = sorted(data_to_clean, key=lambda x: x['{}'.format(self.loc_name_to_get)])
            pnas_list = []
            added_locations = []
            added_programs = []
            added_products_for_locations = {}
            wanted_program = self.config.get('product_program', '')

            for pna in pnas:
                location_name = pna['{}'.format(self.loc_name_to_get)]
                location_id = pna['{}'.format(self.loc_id_to_get)]
                product_name = pna['product_name']
                product_id = pna['product_id']
                program_id = pna['select_programs'].split(' ')
                final_pna_stock_valuation = pna['final_pna_stock_valuation']
                if not final_pna_stock_valuation:
                    final_pna_stock_valuation = 0
                else:
                    final_pna_stock_valuation = final_pna_stock_valuation['sort_key']
                if len(program_id) > 1:
                    for program in program_id:
                        if (program == wanted_program and product_id in self.program_and_products[program]) \
                                or not wanted_program:
                            pna['select_programs'] = program
                            pnas.append(pna.copy())
                else:
                    data_dict = {
                        'location_name': location_name,
                        'location_id': location_id,
                        'program_id': program_id,
                        'products': []
                    }
                    if location_id in added_locations and program_id in added_programs:
                        amount_of_stocks = len(pnas_list)

                        location_position = 0
                        for r in range(0, amount_of_stocks):
                            current_location = pnas_list[r]['location_id']
                            if current_location == location_id:
                                location_position = r
                                break

                        added_products_for_location = \
                            [x['product_id'] for x in added_products_for_locations[location_id]]
                        products_for_location = added_products_for_locations[location_id]
                        if product_id not in added_products_for_location:
                            product_data = {
                                'product_name': product_name,
                                'product_id': product_id,
                                'final_pna_stock_valuation': 0,
                            }
                            added_products_for_locations[location_id].append(product_data)
                            pnas_list[location_position]['products'].append(product_data)

                        amount_of_products_for_location = len(added_products_for_locations[location_id])
                        product_position = 0
                        for s in range(0, amount_of_products_for_location):
                            current_product = products_for_location[s]['product_id']
                            if current_product == product_id:
                                product_position = s
                                break
                        overall_position = pnas_list[location_position]['products'][product_position]
                        overall_position['final_pna_stock_valuation'] += final_pna_stock_valuation
                    else:
                        if isinstance(program_id, list):
                            program_id = program_id[0]
                        if location_id not in added_locations:
                            added_locations.append(location_id)
                        if program_id not in added_programs and \
                            ((program_id == wanted_program and product_id in self.program_and_products[program_id])
                                or not wanted_program):
                            added_programs.append(program_id)
                        if program_id == wanted_program or not wanted_program:
                            product_data = {
                                'product_name': product_name,
                                'product_id': product_id,
                                'final_pna_stock_valuation': 0,
                            }
                            product_data['final_pna_stock_valuation'] += final_pna_stock_valuation
                            data_dict['products'].append(product_data)
                            pnas_list.append(data_dict)
                            added_products_for_locations[location_id] = [product_data]

            pnas_list_to_return = sorted(pnas_list, key=lambda x: x['location_id'])

            return pnas_list_to_return

        clean_data = clean_rows(rows)

        return clean_data


class RecapPassageOneData(IntraHealthSqlData):
    slug = 'recap_passage_1'
    comment = 'recap passage 1'
    title = 'Recap Passage 1'
    show_total = False
    total_row = []
    custom_total_calculate = True

    def __init__(self, config):
        super(RecapPassageOneData, self).__init__()
        self.config = config
        self.product_names = []

    @property
    def engine_id(self):
        return 'ucr'

    @property
    def table_name(self):
        config_domain = self.config['domain']
        doc_id = StaticDataSourceConfiguration.get_doc_id(config_domain, OPERATEUR_COMBINED2)
        config, _ = get_datasource_config(doc_id, config_domain)
        return get_table_name(config_domain, config.table_id)

    @property
    def group_by(self):
        return ['real_date_repeat', 'product_id', 'pps_name', self.loc_id, 'product_name', 'visit']

    @property
    def program_products(self):
        program_id = self.config.get('product_program', None)
        program_products = []
        if program_id:
            programs = ProductsInProgramData(config=dict(domain=self.config['domain'])).rows
            for program in programs:
                if program[0] == program_id:
                    list_of_program_ids = program[1].split(' ')
                    program_products.extend(list_of_program_ids)
            return list(set(program_products))
        else:
            return None

    @property
    def program_name(self):
        program_id = self.config.get('product_program', None)
        domain = self.config['domain']
        if program_id:
            rows = ProgramData(config={'domain': domain, 'program_id': program_id}).rows
            name = next(row[1] for row in rows if row[0] == program_id)
            return name
        else:
            return None

    @property
    def columns(self):
        columns = [
            DatabaseColumn(self.loc_id, SimpleColumn(self.loc_id)),
            DatabaseColumn('PPS Name', SimpleColumn('pps_name')),
            DatabaseColumn("Date", SimpleColumn('real_date_repeat')),
            DatabaseColumn(_("Product name"), SimpleColumn('product_name')),
            DatabaseColumn(_("Product id"), SimpleColumn('product_id')),
            DatabaseColumn(_('Doc_id'), SimpleColumn('doc_id', alias='visit')),
            DatabaseColumn(_("Precedent"), SumColumn('old_stock_pps')),
            DatabaseColumn(_("Old stock total"), SumColumn('old_stock_total')),
            DatabaseColumn(_("Stock disponible et utilisable a la livraison"), SumColumn('total_stock')),
            DatabaseColumn(_("Stock Total"), SumColumn('display_total_stock')),
            DatabaseColumn(_("Outside AMT"), SumColumn('outside_receipts_amt')),
            DatabaseColumn(_("Reelle"), SumColumn('actual_consumption')),
            DatabaseColumn(_("Facturable"), SumColumn('billed_consumption')),
            DatabaseColumn("Pertes et Adjustement", SumColumn('loss_amt')),
            DatabaseColumn("Amount billed", SumColumn('amount_billed')),
            DatabaseColumn("Amt owed", SumColumn('amount_owed')),
            DatabaseColumn("Amt delivered", SumColumn('amt_delivered_convenience')),
            DatabaseColumn("Total loss amt", SumColumn('total_loss_amt')),
            DatabaseColumn("Expired pna", SumColumn('expired_pna')),
            DatabaseColumn("Ajustment", SumColumn('ajustment')),
            DatabaseColumn("Nb days outsotck", SumColumn('nb_days_outstock')),
            DatabaseColumn("Consommations non facturable", SumColumn('consommations_non_facturable')),
            DatabaseColumn("Adjusted monthly consuptions", SumColumn('adjusted_monthly_consumption')),
            DatabaseColumn("PPS stock new", SumColumn('pps_stock_new')),
        ]
        return columns

    @cached_property
    def selected_location(self):
        if self.config['selected_location']:
            return SQLLocation.objects.get(location_id=self.config['selected_location'])
        else:
            return None

    @cached_property
    def selected_location_type(self):
        if not self.selected_location:
            return 'national'
        return self.selected_location.location_type.code

    @cached_property
    def loc_type(self):
        if self.selected_location_type == 'national':
            return 'region'
        if self.selected_location_type == 'region':
            return 'region'
        elif self.selected_location_type == 'district':
            return 'district'
        else:
            return 'pps'

    @cached_property
    def loc_id(self):
        return "{}_id".format(self.loc_type)

    @cached_property
    def loc_name(self):
        return "{}_name".format(self.loc_type)

    @property
    def filters(self):
        filters = [BETWEEN('real_date_repeat', 'startdate', 'enddate')]
        if self.config['selected_location']:
            filters.append(EQ(self.loc_id, 'selected_location'))
        return filters

    def get_value(self, cell):
        if cell:
            return cell['html']
        return 0

    @property
    def rows_and_headers(self):
        rows = self.get_data()
        rows_by_visit = self.sort_rows_by_visit(rows)
        valid_products = self.program_products
        pps_visits = {}
        for doc_id, rows in rows_by_visit.items():
            data = {}
            product_names = set()
            location = rows[0]['pps_name']
            date = rows[0]['real_date_repeat']
            amount_billed_sum = 0

            for row in rows:
                product_name = row['product_name']
                product_id = row['product_id']
                if valid_products and product_id not in valid_products:
                    continue
                product_names.add(product_name)
                if not data.get(product_name):
                    data[product_name] = defaultdict(int)

                product_data = data[product_name]
                product_data['Stock ε PPS Précédent'] += self.get_value(row['old_stock_pps'])
                product_data['Stock Total Précédent'] += self.get_value(row['old_stock_total'])
                product_data['Stock Disponible Utilisable'] += self.get_value(row['total_stock'])
                product_data['Stock Total Restant'] += self.get_value(row['display_total_stock'])
                product_data['Réception Hors Entrepot'] += self.get_value(row['outside_receipts_amt'])
                product_data['Consommations Réelle'] += self.get_value(row['actual_consumption'])
                product_data['Consommations Facturable'] += self.get_value(row['billed_consumption'])
                product_data['Pertes Facturables PNA'] += self.get_value(row['loss_amt'])
                product_data['Facturation Produit'] += self.get_value(row['amount_billed'])
                product_data['Livraison'] += self.get_value(row['amt_delivered_convenience'])
                product_data['Pertes / Péremptions PPS'] += self.get_value(row['total_loss_amt'])
                product_data['Péremptions PNA'] += self.get_value(row['expired_pna'])
                product_data['Ajustements / Retraits PNA'] += self.get_value(row['ajustment'])
                product_data['Nombre Jours de rupture'] += self.get_value(row['nb_days_outstock'])
                product_data['Consommations Non Facturable'] += (
                    self.get_value(row['actual_consumption']) - self.get_value(row['billed_consumption'])
                )
                product_data['CMM Ajustée'] += self.get_value(row['adjusted_monthly_consumption'])
                product_data['Stock Restant ε PPS'] += self.get_value(row['pps_stock_new'])

                amount_billed_sum += self.get_value(row['amount_billed'])

            product_names = sorted(product_names)
            self.product_names = product_names

            rows = []
            if product_names:
                for key in data[product_names[0]]:
                    next_row = [key]
                    for product in product_names:
                        next_row.append(data[product][key])

                    rows.append(next_row)

                facturation_fill = len(rows[0]) - 2
                facturation_group = ['Facturation Groupe', amount_billed_sum]
                facturation_group.extend([' ' for _ in range(facturation_fill)])
                rows.append(facturation_group)

                pps_visits[doc_id] = {
                    'rows': rows,
                    'title': location,
                    'headers': self.get_headers(),
                    'comment': date,
                }

        return pps_visits

    @property
    def aggregated_data(self):
        rows = self.get_data()

        data = {
            'Total Facture': 0,
            'Net à Payer': 0,
        }
        valid_products = self.program_products
        delivery_amt_owed_dict = {}
        for row in rows:
            pps_name = row['pps_name']
            product_name = row['product_name']
            if valid_products and \
                    row['product_id'] not in valid_products:
                continue

            data['Total Facture'] += self.get_value(row['amount_billed'])
            delivery_amt_owed = self.get_value(row['amount_owed'])
            date = row['real_date_repeat'].strftime('%Y/%m/%d')
            self._save_value_if_unique(delivery_amt_owed_dict, pps_name, (delivery_amt_owed, product_name, date))

        data['Total Facture'] = round(float(data['Total Facture']), 2)
        data['Net à Payer'] = round(float(self._sum_up(delivery_amt_owed_dict)), 2)
        rows = []
        headers = data.keys()
        for header in headers:
            value = data[header]
            rows.append([dict(html=value)])

        headers = [DataTablesColumn(header_name) for header_name in headers]
        return rows, DataTablesHeader(*headers)

    @property
    def empty_table(self):
        rows = [['Stock ε PPS Précédent', 'pas de données'],
                ['Stock Total Précédent', 'pas de données'],
                ['Stock Disponible Utilisable', 'pas de données'],
                ['Stock Total Restant', 'pas de données'],
                ['Réception Hors Entrepot', 'pas de données'],
                ['Consommations Réelle', 'pas de données'],
                ['Consommations Facturable', 'pas de données'],
                ['Pertes Facturables PNA', 'pas de données'],
                ['Facturation Produit', 'pas de données'],
                ['Livraison', 'pas de données'],
                ['Pertes / Péremptions PPS', 'pas de données'],
                ['Péremptions PNA', 'pas de données'],
                ['Ajustements / Retraits PNA', 'pas de données'],
                ['Nombre Jours de rupture', 'pas de données'],
                ['Consommations Non Facturable', 'pas de données'],
                ['CMM Ajustée', 'pas de données'],
                ['Stock Restant ε PPS', 'pas de données']]
        empty_headers = DataTablesHeader(DataTablesColumn(''), DataTablesColumn('pas de produits'))
        return rows, empty_headers

    @property
    def headers(self):
        return self.get_headers()

    def get_headers(self):
        headers = DataTablesHeader(DataTablesColumn(''))

        for name in self.product_names:
            headers.add_column(DataTablesColumn(name))
        return headers

    def sort_rows_by_visit(self, rows):
        rows_by_visit = defaultdict(list)
        for row in rows:
            rows_by_visit[row['visit']].append(row)

        return rows_by_visit

    @staticmethod
    def _save_value_if_unique(dictionary, dictionary_key, value):
        if dictionary.get(dictionary_key, None):
            dictionary[dictionary_key].add(value)
        else:
            dictionary[dictionary_key] = set()
            dictionary[dictionary_key].add(value)

    @staticmethod
    def _sum_up(dictionary):
        number = 0
        for values in dictionary.values():
            for value in values:
                number += value[0]

        return number


class RecapPassageTwoData(RecapPassageOneData):
    slug = 'recap_passage_2'
    comment = 'recap passage 2'
    title = 'Recap Passage 2'
    show_total = False
    custom_total_calculate = True

    def __init__(self, config):
        super(RecapPassageTwoData, self).__init__(config)
        self.recap_rows = None
        self.recap_headers = None
        self.latest_pps_doc_ids = None

    @property
    def columns(self):
        columns = super(RecapPassageTwoData, self).columns
        if self.loc_id != 'pps_id':
            columns.extend([
                DatabaseColumn(_('PPS_Id'), SimpleColumn('pps_id'))
            ])
        columns.extend([
            DatabaseColumn(_('Doc_id'), SimpleColumn('doc_id')),
            DatabaseColumn(_('Delivery Margin'), SumColumn('delivery_total_margin')),
        ])
        return columns

    @property
    def group_by(self):
        group = super(RecapPassageTwoData, self).group_by
        if self.loc_id != 'pps_id':
            group.extend(['pps_id'])

        group.extend(['doc_id'])
        return group

    @property
    def program_products(self):
        program_id = self.config.get('product_program', None)
        program_products = []
        if program_id:
            programs = ProductsInProgramData(config=dict(domain=self.config['domain'])).rows
            for program in programs:
                if program[0] == program_id:
                    list_of_program_ids = program[1].split(' ')
                    program_products.extend(list_of_program_ids)
            return list(set(program_products))
        else:
            return None

    @property
    def program_name(self):
        program_id = self.config.get('product_program', None)
        domain = self.config['domain']
        if program_id:
            rows = ProgramData(config={'domain': domain, 'program_id': program_id}).rows
            name = next(row[1] for row in rows if row[0] == program_id)
            return name
        else:
            return None

    def calculate_table_data(self):
        rows = self.get_data()

        product_names = set()
        data = {}
        valid_products = self.program_products

        for row in rows:
            product_name = row['product_name']
            pps_id = row['pps_id']
            product_id = row['product_id']

            if valid_products and product_id not in valid_products:
                continue

            product_names.add(product_name)

            if not data.get(pps_id):
                data[pps_id] = [row]
            else:
                data[pps_id].append(row)

        product_names = sorted(product_names)
        self.product_names = sorted(set(product_names))

        self.recap_rows = data
        self.recap_headers = self.get_headers()

        return data, self.get_headers()

    @property
    def empty_table(self):
        rows = [[name, 'pas de données'] for name in self.product_names]
        empty_headers = DataTablesHeader(DataTablesColumn(''), DataTablesColumn('pas de produits'))
        return rows, empty_headers

    def get_headers(self):
        headers = DataTablesHeader(DataTablesColumn('LISTE des PPS'))

        for name in self.product_names:
            headers.add_column(DataTablesColumn(name))

        return headers


class RecapPassageTwoTables(RecapPassageTwoData):

    def __init__(self, config):
        super(RecapPassageTwoTables, self).__init__(config)

    def create_context(self, **kwargs):
        context = dict(
            title=kwargs.get('title', self.title),
            slug=kwargs.get('slug', self.slug),
            headers=kwargs.get('headers', []),
            rows=kwargs.get('rows', []),
            total_row=kwargs.get('total_row', self.total_row),
            default_rows=kwargs.get('default_rows', None),
            datatables=kwargs.get('datatables', self.datatables),
            fix_column=kwargs.get('fix_left_col', self.fix_left_col))
        return context

    @property
    def sumup_context(self):
        if self.recap_rows is None:
            self.calculate_table_data()

        rows = {
            'Total Versements PPS': dict(html=Decimal(0.0)),
            'Frais Participation PPS': dict(html=Decimal(0.0)),
            'Total Facturation District': dict(html=Decimal(0.0)),
            'Frais Participation District': dict(html=Decimal(0.0)),
            'Total Facturation PRA': dict(html=Decimal(0.0)),
            'Total a Verser a La PRA': dict(html=Decimal(0.0)),
        }
        data = self.recap_rows

        delivery_amt_owed_dict = {}
        for pps in data.keys():
            pps_data = data[pps]

            for element in pps_data:
                product_name = element['product_name']
                if product_name not in self.product_names:
                    continue
                pps_name = element['pps_name']
                date = element['real_date_repeat'].strftime('%Y/%m/%d')

                delivery_amt_owed = element.get('amount_owed', None) or {'html': 0}

                self._save_value_if_unique(
                    delivery_amt_owed_dict, pps_name, (delivery_amt_owed['html'], product_name, date)
                )

        rows['Total Versements PPS']['html'] = self._sum_up(delivery_amt_owed_dict)

        rows['Total Facturation District']['html'] = rows['Total Versements PPS']['html'] / Decimal(1.075)

        rows['Frais Participation PPS']['html'] = rows['Total Facturation District']['html'] * Decimal(0.075)

        rows['Total Facturation PRA']['html'] = rows['Total Facturation District']['html'] / Decimal(1.15)

        rows['Frais Participation District']['html'] = rows['Total Facturation PRA']['html'] * Decimal(0.15 * 0.25)

        rows['Total a Verser a La PRA']['html'] = rows['Total Facturation PRA']['html'] + \
            rows['Frais Participation District']['html'] + rows['Frais Participation PPS']['html']

        row = [["{0:.2f}".format(v['html']) for v in rows.values()]]
        context = self.create_context(
            rows=row, headers=[key for key in rows.keys()],
            title='Recapitulatif Facturation')
        return context

    @property
    def billed_consumption_context(self):
        context = self.create_table_context(
            'billed_consumption', 'Consommations Facturables', add_amount_owed_column=True
        )

        return context

    @property
    def actual_consumption_context(self):
        context = self.create_table_context(
            'actual_consumption', 'Consommation Réelle', add_latest_visit_column=True
        )
        return context

    @property
    def amt_delivered_convenience_context(self):
        context = self.create_table_context(
            'amt_delivered_convenience', 'Livraison Total Effectuées', add_sum_of_visits_column=True
        )
        rows = context['rows']
        new_row = self.create_row_with_column_values_sum('Livraison Effectuées', rows)
        if new_row:
            new_row = new_row[:-1]
        context['rows'].append(new_row)
        return context

    @property
    def display_total_stock_context(self):
        context = self.create_table_context(
            'total_stock', 'Stock Disponible Utilisable', add_availability_column=True
        )
        rows = context['rows']
        sum_row = self.create_row_with_column_values_sum('SDU avant Livraison', rows)
        if sum_row:
            sum_row = sum_row[:-1]
        display_stock_row = self.add_row_with_sum_value('SDU après Livraison', 'display_total_stock')
        context['rows'].append(sum_row)
        context['rows'].append(display_stock_row)
        return context

    def create_table_context(self, displayed_values, title, add_amount_owed_column=False,
                             add_latest_visit_column=False, add_sum_of_visits_column=False,
                             add_availability_column=False):
        if self.recap_rows is None:
            self.calculate_table_data()

        headers = self.get_headers()
        rows = self.create_table_rows(
            displayed_values, add_amount_owed_column=add_amount_owed_column,
            add_latest_visit_column=add_latest_visit_column, add_sum_of_visits_column=add_sum_of_visits_column,
            add_availability_column=add_availability_column
        )

        if add_amount_owed_column:
            headers.add_column(DataTablesColumn('Recouvrement PPS Net à Payer'))
        if add_latest_visit_column:
            headers.add_column(DataTablesColumn('Date Dernier Passage'))
        if add_sum_of_visits_column:
            headers.add_column(DataTablesColumn('Nombre de Passage'))
        if add_availability_column:
            headers.add_column(DataTablesColumn('Taux de Disponibilité de la gamme'))

        context = self.create_context(
            rows=rows, headers=headers, title=title
        )

        return context

    def create_table_rows(self, displayed_values, add_amount_owed_column=False, add_latest_visit_column=False,
                          add_sum_of_visits_column=False, add_availability_column=False):
        rows = []
        data = self.recap_rows
        total_row = ['SYNTHESE']
        values_for_total_row = {}
        average_availability = {}

        if add_amount_owed_column or add_latest_visit_column:
            add_total_row = True
        else:
            add_total_row = False

        for pps in data.keys():
            pps_data = data[pps]
            pps_name = pps_data[0]['pps_name']
            row = [pps_name]

            most_recent_pps_data = self._get_most_recent_visits(pps_data)
            pps_product_values = self.get_row_product_values(pps_data, displayed_values)
            for name in self.product_names:
                product_value = pps_product_values.get(name, {'html': 0})
                if add_total_row:
                    self._collect_value(values_for_total_row, name, product_value)

                row.append(product_value)

            if add_amount_owed_column:
                amount_sum = self._get_amount_owed(pps_data)
                self._collect_value(values_for_total_row, 'Recouvrement PPS Net à Payer', amount_sum)

                row.append(amount_sum)

            if add_latest_visit_column:
                latest_date = self._get_latest_date(most_recent_pps_data)

                row.append(latest_date)

            if add_sum_of_visits_column:
                visits_for_pps = self._get_visits_for_pps(pps_data)

                row.append(visits_for_pps)

            if add_availability_column:
                self._collect_availability(average_availability, pps_data)

            rows.append(row)

        if add_total_row:
            for key, value in values_for_total_row.items():
                total_row.append({'html': value})
            rows.append(total_row)

        if add_availability_column:
            self._append_availability_to_rows(rows, average_availability)

        return rows

    def get_row_product_values(self, pps_data, column):
        product_value = {}
        for row in pps_data:
            key = row['product_name']
            value = row.get(column, {'html': 0})['html']
            if key in product_value:
                product_value[key]['html'] += value
            else:
                product_value[key] = {'html': value}
        return product_value

    def create_row_with_column_values_sum(self, row_name, rows, title_column=True):
        if len(rows) == 0:
            return None

        new_row = [row_name]
        rows = rows if not title_column else [row[1:] for row in rows]
        number_of_columns = len(rows[0])

        row_values = [0 for column in range(0, number_of_columns)]
        for row in rows:
            for index, column_value in enumerate(row):
                row_values[index] += column_value['html'] if not column_value.get('percent', False) else 0

        new_row.extend(row_values)
        return new_row

    def add_row_with_sum_value(self, row_name, value_name):
        rows = self.create_table_rows(value_name, False)
        sum_row = self.create_row_with_column_values_sum(row_name, rows)
        return sum_row

    @staticmethod
    def _get_most_recent_visits(data):
        data_to_return = []
        fresh_records_dict = {}
        for row in data:
            pps_name = row['pps_name']
            product_id = row['product_id']
            if pps_name not in fresh_records_dict.keys():
                fresh_records_dict[pps_name] = {
                    product_id: row
                }
            else:
                if product_id not in fresh_records_dict[pps_name].keys():
                    fresh_records_dict[pps_name][product_id] = row
                else:
                    date = fresh_records_dict[pps_name][product_id]['real_date_repeat']
                    new_date = row['real_date_repeat']
                    if new_date > date:
                        fresh_records_dict[pps_name][product_id] = row

        for pps_name, products in fresh_records_dict.items():
            for product, product_data in products.items():
                data_to_return.append(product_data)

        return data_to_return

    @staticmethod
    def _get_latest_date(data):
        return data[0]['real_date_repeat'].strftime('%Y/%m/%d')

    @staticmethod
    def _get_visits_for_pps(data):
        visits = set()
        for record in data:
            visits.add(record['doc_id'])

        return {'html': len(visits)}

    def _collect_availability(self, availability_dict, data):
        products_amount = len(self.product_names)
        for row in data:
            date_repeat = row['real_date_repeat'].strftime('%Y/%m/%d')
            pps_name = row['pps_name']
            in_stock = 1 if row['total_stock']['html'] else 0
            if availability_dict.get(pps_name):
                if availability_dict[pps_name].get(date_repeat):
                    availability_dict[pps_name][date_repeat][0] += in_stock
                else:
                    availability_dict[pps_name][date_repeat] = [in_stock, products_amount]
            else:
                availability_dict[pps_name] = {
                    date_repeat: [in_stock, products_amount]
                }

    @staticmethod
    def _get_amount_owed(ppses_data):
        to_return = 0
        elements = []
        for el in ppses_data:
            el_name = el['pps_name']
            amount = el.get('amount_owed', {'html': 0})['html']
            date = el['real_date_repeat'].strftime('%Y/%m/%d')
            product_name = el['product_name']
            el_data = (amount, product_name, date, el_name)
            if el_data not in elements:
                elements.append(el_data)
                to_return += amount

        return {'html': to_return}

    @staticmethod
    def _collect_value(values_dict, key, product_value):
        value = product_value['html']
        if values_dict.get(key, None):
            values_dict[key] += value
        else:
            values_dict[key] = value

    @staticmethod
    def _append_availability_to_rows(collected_rows, availability_dict):
        for row in collected_rows:
            pps_name = row[0]
            dates = availability_dict[pps_name]
            average = 0
            for date, availability in dates.items():
                average += (availability[0] / availability[1]) * 100
            average = round((float(average) / len(dates)), 2)
            row.append({
                'html': f'{average}%',
                'percent': True,
            })


class IndicateursDeBaseData(SqlData, LocationLevelMixin):
    slug = 'indicateurs_de_base'
    comment = ''
    title = 'Indicateur de Base'
    show_total = True
    custom_total_calculate = True

    def __init__(self, config):
        super(IndicateursDeBaseData, self).__init__()
        self.config = config

    @property
    def engine_id(self):
        return 'ucr'

    @property
    def table_name(self):
        config_domain = self.config['domain']
        doc_id = StaticDataSourceConfiguration.get_doc_id(config_domain, INDICATEURS_DE_BASE)
        config, _ = get_datasource_config(doc_id, config_domain)
        return get_table_name(config_domain, config.table_id)

    @property
    def group_by(self):
        return [
            self.loc_id_to_get, self.loc_name_to_get,
            'date_prevue_livraison_debut',
            'date_prevue_livraison_fin', 'nb_pps_enregistres',
            'nb_pps_visites'
        ]

    @property
    def columns(self):
        columns = [
            DatabaseColumn('Location ID', SimpleColumn(self.loc_id_to_get)),
            DatabaseColumn('Location Name', SimpleColumn(self.loc_name_to_get)),
            DatabaseColumn('Date (Start)', SimpleColumn('date_prevue_livraison_debut')),
            DatabaseColumn('Date (End)', SimpleColumn('date_prevue_livraison_fin')),
            DatabaseColumn("NB PPS Enregistres", SimpleColumn('nb_pps_enregistres')),
            DatabaseColumn("NB PPS Visites", SimpleColumn('nb_pps_visites')),
        ]
        return columns

    @cached_property
    def loc_type(self):
        if self.selected_location_type in ['national', 'region']:
            return 'region'
        else:
            return 'district'

    @cached_property
    def loc_type_to_get(self):
        if self.selected_location_type == 'national':
            return 'region'
        else:
            return 'district'

    @property
    def month(self):
        if self.config['month']:
            return int(self.config['month'])
        return 1

    @property
    def year(self):
        if self.config['year']:
            return int(self.config['year'])
        return 2008

    @property
    def min_date(self):
        month = self.month
        year = self.year
        min_date = datetime.date(year, month, 1)

        return min_date

    @property
    def max_date(self):

        def last_day_of_month(any_day):
            next_month = any_day.replace(day=28) + datetime.timedelta(days=4)
            return next_month - datetime.timedelta(days=next_month.day)

        max_date = last_day_of_month(self.min_date)

        return max_date

    def is_requested_location(self, location_name):
        if self.config['location_id']:
            try:
                location = SQLLocation.objects.get(domain=self.config['domain'],
                                                   location_id=self.config['location_id'])
            except SQLLocation.DoesNotExist:
                return False
            if location.location_type.name != 'District':
                location = SQLLocation.objects.filter(domain=self.config['domain'],
                                                      parent=location.id)
                location = [l.name for l in location]
            else:
                location = [location.name]

            return location_name in location
        else:
            return True

    @property
    def filters(self):
        filters = []

        return filters

    @property
    def rows(self):
        rows = self.get_data()

        rows_with_wanted_date = []
        for row in rows:
            min_date = row['date_prevue_livraison_debut']
            max_date = row['date_prevue_livraison_fin']

            location_name = row[self.loc_name_to_get]
            if min_date >= self.min_date and max_date <= self.max_date \
                    and self.is_requested_location(location_name):
                rows_with_wanted_date.append(row)

        for row in rows_with_wanted_date:
            if row[self.loc_id_to_get] is None:
                row[self.loc_id_to_get] = SQLLocation.objects.get(
                    domain=self.config['domain'],
                    name=row[self.loc_name_to_get]).location_id

        def clean_rows(data_to_clean):
            for data_row in data_to_clean:
                data_row[self.loc_name_to_get] = data_row.get(self.loc_name_to_get, '')
                data_row[self.loc_id_to_get] = data_row.get(self.loc_id_to_get, '')

            sorted_rows = sorted(data_to_clean, key=lambda x: x.get(self.loc_name_to_get, ' '))
            added_locations = []
            data_for_locations = {}
            data_to_return = []

            for row in sorted_rows:
                location_id = row[self.loc_id_to_get]
                location_name = row[self.loc_name_to_get]
                if location_id is None:
                    location_id = location_name
                nb_pps_enregistres = row['nb_pps_enregistres']
                nb_pps_visites = row['nb_pps_visites']
                tmp_min_date = row['date_prevue_livraison_debut']
                tmp_max_date = row['date_prevue_livraison_fin']
                if location_id not in added_locations:
                    added_locations.append(location_id)
                    data_for_locations[location_id] = {
                        'location_name': location_name,
                        'min_date': tmp_min_date,
                        'max_date': tmp_max_date,
                        'nb_pps_enregistres': nb_pps_enregistres,
                        'nb_pps_visites': nb_pps_visites,
                    }
                else:
                    data_for_locations[location_id]['nb_pps_enregistres'] += nb_pps_enregistres
                    data_for_locations[location_id]['nb_pps_visites'] += nb_pps_visites
                    current_min_date = data_for_locations[location_id]['min_date']
                    current_max_date = data_for_locations[location_id]['max_date']
                    if tmp_min_date < current_min_date:
                        data_for_locations[location_id]['min_date'] = tmp_min_date
                    if tmp_max_date < current_max_date:
                        data_for_locations[location_id]['max_date'] = tmp_max_date

            for location_id, location_info in data_for_locations.items():
                data_to_return.append({
                    'location_id': location_id,
                    'location_name': location_info['location_name'],
                    'min_date': location_info['min_date'],
                    'max_date': location_info['max_date'],
                    'nb_pps_enregistres': location_info['nb_pps_enregistres'],
                    'nb_pps_visites': location_info['nb_pps_visites'],
                })

            return data_to_return

        clean_data = clean_rows(rows_with_wanted_date)

        return clean_data
