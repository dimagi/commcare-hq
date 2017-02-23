from collections import namedtuple

from sqlagg.filters import IN, AND, GTE, LT, EQ

from corehq.apps.reports.filters.dates import DatespanFilter
from corehq.apps.reports.generic import GenericReportView
from corehq.apps.reports.sqlreport import SqlTabularReport, SqlData
from corehq.apps.reports.standard import CustomProjectReport, DatespanMixin
from corehq.apps.reports.util import get_INFilter_bindparams
from corehq.apps.userreports.util import get_table_name
from corehq.sql_db.connections import UCR_ENGINE_ID
from custom.enikshay.reports.filters import EnikshayLocationFilter, EnikshayMigrationFilter
from custom.utils.utils import clean_IN_filter_value

TABLE_ID = 'episode'

EnikshayReportConfig = namedtuple('ReportConfig', ['domain', 'locations_id', 'is_migrated', 'start_date', 'end_date'])


class MultiReport(CustomProjectReport, GenericReportView):
    report_template_path = 'enikshay/multi_report.html'

    @property
    def reports(self):
        raise NotImplementedError()

    @property
    def report_context(self):
        context = {
            'reports': []
        }
        for report in self.reports:
            report.fields = self.fields
            report_instance = report(self.request, domain=self.domain)
            report_context = report_instance.report_context
            report_table = report_context.get('report_table', {})
            report_table['slug'] = report_instance.slug
            context['reports'].append({
                'report': report_instance.context.get('report', {}),
                'report_table': report_table
            })
        return context


class EnikshayMultiReport(MultiReport):
    fields = (DatespanFilter, EnikshayLocationFilter, EnikshayMigrationFilter)

    @property
    def export_table(self):
        export_table = []

        for report in self.reports:
            report_instance = report(self.request, domain=self.domain)
            rows = [
                [header.html for header in report_instance.headers.header]
            ]
            report_table = [
                unicode(report.name[:28] + '...'),
                rows
            ]
            export_table.append(report_table)

            for row in report_instance.rows:
                row_formatted = []
                for element in row:
                    if isinstance(element, dict):
                        row_formatted.append(element['sort_key'])
                    else:
                        row_formatted.append(unicode(element))
                rows.append(row_formatted)
        return export_table


class EnikshayReport(DatespanMixin, CustomProjectReport, SqlTabularReport):
    use_datatables = False

    @property
    def report_config(self):
        is_migrated = EnikshayMigrationFilter.get_value(self.request, self.domain)
        if is_migrated is not None:
            is_migrated = int(is_migrated)
        return EnikshayReportConfig(
            domain=self.domain,
            locations_id=EnikshayLocationFilter.get_value(self.request, self.domain),
            is_migrated=is_migrated,
            start_date=self.datespan.startdate,
            end_date=self.datespan.end_of_end_day
        )


class EnikshaySqlData(SqlData):

    @property
    def engine_id(self):
        return UCR_ENGINE_ID

    @property
    def table_name(self):
        return get_table_name(self.config.domain, TABLE_ID)

    @property
    def filter_values(self):
        filter_values = {
            'start_date': self.config.start_date,
            'end_date': self.config.end_date,
            'locations_id': self.config.locations_id,
            'is_migrated': self.config.is_migrated,
        }
        clean_IN_filter_value(filter_values, 'locations_id')
        return filter_values

    @property
    def group_by(self):
        return []

    @property
    def filters(self):
        filters = [
            AND([GTE('opened_on', 'start_date'), LT('opened_on', 'end_date')])
        ]

        locations_id = filter(lambda x: bool(x), self.config.locations_id)

        if locations_id:
            filters.append(
                IN('person_owner_id', get_INFilter_bindparams('locations_id', locations_id))
            )

        is_migrated = self.config.is_migrated

        if is_migrated is not None:
            filters.append(EQ('case_created_by_migration', 'is_migrated'))

        return filters
