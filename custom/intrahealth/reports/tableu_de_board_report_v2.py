from corehq.apps.reports.filters.dates import DatespanFilter
from corehq.apps.reports.standard import CustomProjectReport, ProjectReportParametersMixin, DatespanMixin
from custom.intrahealth.filters import YeksiNaaLocationFilter2
from custom.intrahealth.reports.utils import IntraHealthLocationMixin, IntraHealthReportConfigMixin
from custom.intrahealth.sqldata import ConventureData2, PPSAvecDonnees2, DispDesProducts2, ConsommationData2, \
    TauxDeRuptures2, TauxConsommationData2, NombreData2, GestionDeLIPMTauxDeRuptures2, DureeData2, \
    RecouvrementDesCouts2
from memoized import memoized
from corehq.apps.locations.models import SQLLocation


class MultiReport(CustomProjectReport, IntraHealthLocationMixin, IntraHealthReportConfigMixin,
                  ProjectReportParametersMixin, DatespanMixin):

    title = ''
    base_template_path = "intrahealth/base_multi_report.html"
    report_template_path = "intrahealth/multi_report.html"
    flush_layout = True
    export_format_override = 'csv'

    @property
    @memoized
    def rendered_report_title(self):
        return self.title

    @property
    @memoized
    def data_providers(self):
        return []

    @property
    def report_context(self):
        context = {
            'reports': [self.get_report_context(dp) for dp in self.data_providers],
            'title': self.title
        }

        return context

    def get_report_context(self, data_provider):

        total_row = []
        self.data_source = data_provider
        if self.needs_filters:
            headers = []
            rows = []
        else:
            rows = data_provider.rows
            headers = data_provider.headers
            total_row = data_provider.total_row

        context = dict(
            report_table=dict(
                title=data_provider.title,
                slug=data_provider.slug,
                headers=headers,
                rows=rows,
                total_row=total_row,
                default_rows=self.default_rows,
                datatables=data_provider.datatables,
                fix_column=data_provider.fix_left_col
            )
        )

        return context

    @property
    def export_table(self):
        reports = [r['report_table'] for r in self.report_context['reports']]
        return [self._export_table(r['title'], r['headers'], r['rows'], total_row=r['total_row']) for r in reports]

    def _export_table(self, export_sheet_name, headers, formatted_rows, total_row=None):
        def _unformat_row(row):
            return [col.get("sort_key", col) if isinstance(col, dict) else col for col in row]

        table = headers.as_export_table
        rows = [_unformat_row(row) for row in formatted_rows]
        replace = ''

        #make headers and subheaders consistent
        for k, v in enumerate(table[0]):
            if v != ' ':
                replace = v
            else:
                table[0][k] = replace
        table.extend(rows)
        if total_row:
            table.append(_unformat_row(total_row))

        return [export_sheet_name, table]


class TableuDeBoardReport2(MultiReport):
    title = "Tableau De Bord NEW"
    fields = [DatespanFilter, YeksiNaaLocationFilter2]
    name = "Tableau De Bord NEW"
    slug = 'tableu_de_board2'
    default_rows = 10
    exportable = True

    @property
    @memoized
    def data_providers(self):
        config = self.report_config
        locations = []

        if 'region_id' in config:
            locations = tuple(SQLLocation.objects.get(
                location_id=config['region_id']
            ).archived_descendants().values_list('location_id', flat=True))
        elif 'district_id' in config:
            locations = tuple(SQLLocation.objects.get(
                location_id=config['district_id']
            ).archived_descendants().values_list('location_id', flat=True))

        if locations:
            config.update({'archived_locations': locations})

        if 'district_id' in config:
            return [
                ConventureData2(config=config),
                PPSAvecDonnees2(config=config),
                TauxDeRuptures2(config=config),
                ConsommationData2(config=config),
                TauxConsommationData2(config=config),
                NombreData2(config=config),
                GestionDeLIPMTauxDeRuptures2(config=config),
                RecouvrementDesCouts2(config=config),
            ]
        else:
            return [
                ConventureData2(config=config),
                PPSAvecDonnees2(config=config),
                DispDesProducts2(config=config),
                TauxDeRuptures2(config=config),
                ConsommationData2(config=config),
                TauxConsommationData2(config=config),
                NombreData2(config=config),
                GestionDeLIPMTauxDeRuptures2(config=config),
                DureeData2(config=config),
                RecouvrementDesCouts2(config=config),
            ]
