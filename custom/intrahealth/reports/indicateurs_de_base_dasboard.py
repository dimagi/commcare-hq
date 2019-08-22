# coding=utf-8
from __future__ import absolute_import
from __future__ import unicode_literals
from __future__ import division

from django.utils.functional import cached_property

from corehq.apps.locations.models import SQLLocation, get_location
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn
from corehq.apps.reports.standard import CustomProjectReport
from custom.intrahealth.filters import YeksiNaaLocationFilter, FRMonthFilter, FRYearFilter
from custom.intrahealth.report_calcs import _locations_per_type
from custom.intrahealth.reports.utils import YeksiNaaMonthYearMixin
from custom.intrahealth.sqldata import IndicateursDeBaseData


class IndicateursDeBaseReport(CustomProjectReport, YeksiNaaMonthYearMixin):
    slug = 'indicateurs_de_base'
    comment = 'indicateurs de base'
    name = 'Indicateurs de Base'
    default_rows = 10
    report_template_path = 'yeksi_naa/tabular_report.html'

    @property
    def fields(self):
        return [FRMonthFilter, FRYearFilter, YeksiNaaLocationFilter]

    @cached_property
    def rendered_report_title(self):
        return self.name

    @property
    def report_context(self):
        context = {
            'report': self.get_report_context(),
            'title': self.name
        }

        return context

    @property
    def selected_location(self):
        try:
            return SQLLocation.objects.get(location_id=self.request.GET.get('location_id'))
        except SQLLocation.DoesNotExist:
            return None

    @property
    def selected_location_type(self):
        if self.selected_location:
            location_type = self.selected_location.location_type.code
            if location_type == 'region':
                return 'District'
            else:
                return 'PPS'
        else:
            return 'Region'

    @property
    def headers(self):
        headers = DataTablesHeader(
            DataTablesColumn(self.selected_location_type),
            DataTablesColumn('Date effective de livraison'),
            DataTablesColumn('Nombre de PPS enregistrés'),
            DataTablesColumn('Nombre de PPS visités'),
            DataTablesColumn('Taux de couverture'),
            DataTablesColumn('Taux de soumission')
        )

        return headers

    def get_report_context(self):
        if self.needs_filters:
            headers = []
            rows = []
        else:
            rows = self.calculate_rows()
            headers = self.headers

        context = dict(
            report_table=dict(
                title=self.name,
                slug=self.slug,
                comment=self.comment,
                headers=headers,
                rows=rows,
                default_rows=self.default_rows,
            )
        )

        return context

    def calculate_rows(self):
        rows = IndicateursDeBaseData(config=self.config).rows
        rows_to_return = []

        for row in rows:
            location_name = row['location_name']

            min_date = row['min_date']
            max_date = row['max_date']
            date = '{} - {}'.format(min_date, max_date)

            nb_pps_enregistres = row['nb_pps_enregistres']
            nb_pps_visites = row['nb_pps_visites']
            couverture = '{:.2f} %'.format((nb_pps_visites / nb_pps_enregistres) * 100) \
                if nb_pps_enregistres is not 0 else 'pas de données'

            loc = get_location(row['location_id'], domain=self.config['domain'])
            no_de_pps_aces_donnes_soumies = _locations_per_type(self.config['domain'], 'PPS', loc)
            soumission = '{:.2f} %'.format((no_de_pps_aces_donnes_soumies / nb_pps_visites) * 100) \
                if nb_pps_visites is not 0 else 'pas de données'

            columns_for_location = [date, nb_pps_enregistres, nb_pps_visites, couverture, soumission]
            rows_to_return.append([
                location_name,
            ])

            for column in columns_for_location:
                rows_to_return[-1].append({
                    'html': '{}'.format(column),
                    'sort_key': column,
                })

        return rows_to_return

    @property
    def config(self):
        config = dict(
            domain=self.domain,
        )
        config['month'] = self.request.GET.get('month')
        config['year'] = self.request.GET.get('year')
        config['product_program'] = self.request.GET.get('product_program')
        config['product_product'] = self.request.GET.get('product_product')
        config['selected_location'] = self.request.GET.get('location_id')
        return config
