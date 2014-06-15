from sqlagg.base import AliasColumn
from sqlagg.columns import SumColumn, MaxColumn, SimpleColumn, CountColumn

from corehq.apps.reports.datatables import DataTablesColumn
from corehq.apps.reports.sqlreport import DataFormatter, \
    TableDataFormat
from sqlagg.filters import EQ, NOTEQ, BETWEEN
from corehq.apps.reports.sqlreport import DatabaseColumn, SqlData, AggregateColumn
from django.utils.translation import ugettext as _


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
        if 'region_id' in self.config:
            return ['region_id']
        elif 'district_id' in self.config:
            return ['district_id']
        else:
            return []

    @property
    def external_rows(self):
        return [[u'Command\xe9e'], [u'Reau'], [u'Taux']]

    @property
    def external_columns(self):
        return [DataTablesColumn(u"Quantit\xe9")]

    @property
    def rows(self):
        rows = super(DispDesProducts, self).rows
        def chunk(rows, n):
            for i in xrange(0, len(rows), n):
                yield rows[i:i+n]

        return map(list.__add__, self.external_rows, chunk(rows[0], len(rows[0])/3)) if rows else [[]]

    @property
    def columns(self):
        a = {'visible': False}
        return [

            DatabaseColumn(u"DIU", SumColumn('diu_commandes_total', alias='diu_commandes')),
            DatabaseColumn(u"Implant", SumColumn('implant_commandes_total', alias='implant_commandes')),
            DatabaseColumn(u"Injectable", SumColumn('injectable_commandes_total', alias='injectable_commandes')),
            DatabaseColumn(u"Microlut", SumColumn('microlut_commandes_total', alias='microlut_commandes')),
            DatabaseColumn(u"Microgynon", SumColumn('microgynon_commandes_total', alias='microgynon_commandes')),
            DatabaseColumn(u"Pr\xe9servatif Masculin", SumColumn('masculin_commandes_total', alias='masculin_commandes')),
            DatabaseColumn(u"Pr\xe9servatif F\xe9minin", SumColumn('feminin_commandes_total', alias='feminin_commandes')),
            DatabaseColumn(u"CU", SumColumn('cu_commandes_total', alias='cu_commandes')),
            DatabaseColumn(u"Collier", SumColumn('collier_commandes_total', alias='collier_commandes')),
            DatabaseColumn(u"DIU_r", SumColumn('diu_recus_total', alias='diu_recus'), **a),
            DatabaseColumn(u"Implant_r", SumColumn('implant_recus_total', alias='implant_recus'), **a),
            DatabaseColumn(u"Injectable_r", SumColumn('injectable_recus_total', alias='injectable_recus'), **a),
            DatabaseColumn(u"Microlut_r", SumColumn('microlut_recus_total', alias='microlut_recus'), **a),
            DatabaseColumn(u"Microgynon_r", SumColumn('microgynon_recus_total', alias='microgynon_recus'), **a),
            DatabaseColumn(u"Pr\xe9servatif Masculin_r", SumColumn('masculin_recus_total', alias='masculin_recus'), **a),
            DatabaseColumn(u"Pr\xe9servatif F\xe9minin_r", SumColumn('feminin_recus_total', alias='feminin_recus'), **a),
            DatabaseColumn(u"CU_r", SumColumn('cu_recus_total', alias='cu_recus'), **a),
            DatabaseColumn(u"Collier_r", SumColumn('collier_recus_total', alias='collier_recus'), **a),
            AggregateColumn(u"DIU_t", self.percent_fn,
                            [AliasColumn('diu_commandes'), AliasColumn('diu_recus')], **a),
            AggregateColumn(u"Implant_r", self.percent_fn,
                            [AliasColumn('implant_commandes'), AliasColumn('implant_recus')], **a),
            AggregateColumn(u"Injectable_r", self.percent_fn,
                            [AliasColumn('injectable_commandes'), AliasColumn('injectable_recus')], **a),
            AggregateColumn(u"Microlut_r", self.percent_fn,
                            [AliasColumn('microlut_commandes'), AliasColumn('microlut_recus')], **a),
            AggregateColumn(u"Microgynon_r", self.percent_fn,
                            [AliasColumn('microgynon_commandes'), AliasColumn('microgynon_recus')], **a),
            AggregateColumn(u"Pr\xe9servatif Masculin_r", self.percent_fn,
                            [AliasColumn('masculin_commandes'), AliasColumn('masculin_recus')], **a),
            AggregateColumn(u"Pr\xe9servatif F\xe9minin_r", self.percent_fn,
                            [AliasColumn('feminin_commandes'), AliasColumn('feminin_recus')], **a),
            AggregateColumn(u"CU_r", self.percent_fn,
                            [AliasColumn('cu_commandes'), AliasColumn('cu_recus')], **a),
            AggregateColumn(u"Collier_r", self.percent_fn,
                            [AliasColumn('collier_commandes'), AliasColumn('collier_recus')], **a),
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