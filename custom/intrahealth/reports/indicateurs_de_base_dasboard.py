# coding=utf-8

from django.utils.functional import cached_property

from corehq.apps.locations.models import SQLLocation, get_location
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn
from corehq.apps.reports.standard import CustomProjectReport
from custom.intrahealth.filters import FRMonthFilter, FRYearFilter, IndicateursDeBaseLocationFilter
from custom.intrahealth.report_calcs import _locations_per_type
from custom.intrahealth.reports.utils import YeksiNaaMonthYearMixin
from custom.intrahealth.sqldata import IndicateursDeBaseData


class IndicateursDeBaseReport(CustomProjectReport, YeksiNaaMonthYearMixin):
    slug = 'planning_couverture_soumission_report'
    comment = 'Planning - Couverture - Soumission'
    name = 'Planning - Couverture - Soumission'
    default_rows = 10
    exportable = True

    report_template_path = 'yeksi_naa/tabular_report.html'

    @property
    def export_table(self):
        report = [
            [
                self.name,
                [],
            ]
        ]
        headers = [
            self.selected_location_type,
            'Date effective de livraison',
            'Nombre de PPS enregistrés',
            'Nombre de PPS visités',
            'Nombre de PPS données soumises',
            'Taux de couverture',
            'Taux de soumission',
        ]
        rows = self.calculate_rows()
        report[0][1].append(headers)

        for row in rows:
            location_name = row[0]
            location_name = location_name.replace('<b>', '')
            location_name = location_name.replace('</b>', '')

            row_to_return = [location_name]

            rows_length = len(row)
            for r in range(1, rows_length):
                value = row[r]['html']
                value = value.replace('<b>', '')
                value = value.replace('</b>', '')
                row_to_return.append(value)

            report[0][1].append(row_to_return)

        return report

    @property
    def fields(self):
        return [FRMonthFilter, FRYearFilter, IndicateursDeBaseLocationFilter]

    @cached_property
    def rendered_report_title(self):
        return self.name

    @property
    def report_context(self):
        if not self.needs_filters:
            return {
                'report': self.get_report_context(),
                'title': self.name
            }
        return {}

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
            DataTablesColumn('Nombre de PPS données soumises'),
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

        context = {
            'report_table': {
                'title': self.name,
                'slug': self.slug,
                'comment': self.comment,
                'headers': headers,
                'rows': rows,
                'default_rows': self.default_rows,
            }
        }

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
                if nb_pps_enregistres != 0 else 'pas de données'

            if row['location_id']:
                loc = get_location(row['location_id'], domain=self.config['domain'])
                no_de_pps_aces_donnes_soumies = _locations_per_type(self.config['domain'], 'PPS', loc)
                soumission = '{:.2f} %'.format((no_de_pps_aces_donnes_soumies / nb_pps_visites) * 100) \
                    if nb_pps_visites != 0 else 'pas de données'
            else:
                no_de_pps_aces_donnes_soumies = 'pas de données'
                soumission = 'pas de données'

            columns_for_location = [
                date, nb_pps_enregistres, nb_pps_visites,
                no_de_pps_aces_donnes_soumies, couverture, soumission
            ]
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
        config = {
            'domain': self.domain,
        }
        config['month'] = self.request.GET.get('month')
        config['year'] = self.request.GET.get('year')
        config['location_id'] = self.request.GET.get('location_id')
        return config
