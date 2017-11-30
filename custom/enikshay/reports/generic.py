from __future__ import absolute_import
from collections import namedtuple

from datetime import datetime

from sqlagg.filters import IN, AND, GTE, LT, EQ

from corehq.apps.reports.filters.base import BaseMultipleOptionFilter, BaseSingleOptionFilter
from corehq.apps.reports.filters.dates import DatespanFilter
from corehq.apps.reports.generic import GenericReportView
from corehq.apps.reports.sqlreport import SqlTabularReport, SqlData
from corehq.apps.reports.standard import CustomProjectReport, DatespanMixin
from corehq.apps.reports.util import get_INFilter_bindparams
from corehq.apps.userreports.util import get_table_name
from corehq.sql_db.connections import UCR_ENGINE_ID
from corehq.util.timezones.utils import get_timezone_for_domain
from custom.enikshay.reports.filters import EnikshayLocationFilter, EnikshayMigrationFilter
from custom.utils.utils import clean_IN_filter_value

from django.utils.translation import ugettext as _
import six

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


class EnikshayMultiReport(MultiReport, DatespanMixin):
    fields = (DatespanFilter, EnikshayLocationFilter, EnikshayMigrationFilter)

    def _get_filter_values(self):
        for field in self.fields:
            field_instance = field(request=self.request, domain=self.domain)
            if isinstance(field_instance, DatespanFilter):
                value = field_instance.datespan.default_serialization()
            elif isinstance(field_instance, BaseMultipleOptionFilter):
                value = ', '.join([s.get('text', '') for s in field_instance.selected])
            elif isinstance(field_instance, BaseSingleOptionFilter):
                filter_value = field_instance.selected
                if not filter_value:
                    value = six.text_type(field_instance.default_text)
                else:
                    value = [
                        display_text
                        for option_value, display_text in field_instance.options
                        if option_value == filter_value
                    ][0]
            else:
                value = six.text_type(field_instance.get_value(self.request, self.domain))
            yield six.text_type(field.label), value

    @property
    def export_table(self):
        export_table = []
        tz = get_timezone_for_domain(self.domain)

        self._get_filter_values()
        metadata = [
            _('metadata'),
            [
                [_('Report Name'), self.name],
                [
                    _('Generated On'), datetime.now(tz=tz).strftime('%Y-%m-%d %H:%M')
                ],
            ] + list(self._get_filter_values())
        ]

        export_table.append(metadata)

        for report in self.reports:
            report_instance = report(self.request, domain=self.domain)
            rows = [
                [header.html for header in report_instance.headers.header]
            ]
            report_table = [
                six.text_type(report.name[:28] + '...'),
                rows
            ]
            export_table.append(report_table)

            for row in report_instance.rows:
                row_formatted = []
                for element in row:
                    if isinstance(element, dict):
                        row_formatted.append(element['sort_key'])
                    else:
                        row_formatted.append(six.text_type(element))
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
    def date_property(self):
        return 'opened_on'

    @property
    def location_property(self):
        return 'person_owner_id'

    @property
    def filters(self):
        filters = [
            AND([GTE(self.date_property, 'start_date'), LT(self.date_property, 'end_date')])
        ]

        locations_id = filter(lambda x: bool(x), self.config.locations_id)

        if locations_id:
            filters.append(
                IN(self.location_property, get_INFilter_bindparams('locations_id', locations_id))
            )

        is_migrated = self.config.is_migrated

        if is_migrated is not None:
            filters.append(EQ('case_created_by_migration', 'is_migrated'))

        return filters
