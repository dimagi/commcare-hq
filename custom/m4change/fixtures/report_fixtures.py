import calendar
from datetime import datetime

from dateutil.relativedelta import relativedelta
from lxml import etree as ElementTree
from django.utils.translation import ugettext as _

from corehq.apps.domain.models import Domain
from corehq.apps.commtrack.util import get_commtrack_location_id
from corehq.apps.locations.models import Location
from custom.m4change.constants import M4CHANGE_DOMAINS, NUMBER_OF_MONTHS_FOR_FIXTURES
from custom.m4change.models import FixtureReportResult
from custom.m4change.reports.reports import M4ChangeReportDataSource
from dimagi.utils.parsing import json_format_date


def get_last_n_months(months):
    ranges = []
    today = datetime.utcnow()
    for month in range(months):
        month_start = datetime(today.year, today.month, 1) - relativedelta(months=month)
        last_day_of_month = get_last_day_of_month(month_start, today)
        month_end = datetime(month_start.year, month_start.month, last_day_of_month)
        ranges.insert(0, (month_start, month_end))
    return ranges


def get_last_month():
    return get_last_n_months(1)[0]


def get_last_day_of_month(month_start, today):
    return today.day if month_start.month == today.month else calendar.monthrange(month_start.year, month_start.month)[1]


class ReportFixtureProvider(object):
    id = 'reports:m4change-mobile'

    def __call__(self, user, version, last_sync=None, app=None):
        if user.domain in M4CHANGE_DOMAINS:
            domain = Domain.get_by_name(user.domain)
            location_id = get_commtrack_location_id(user, domain)
            if location_id is not None:
                fixture = self.get_fixture(user, domain, location_id)
                if fixture is None:
                    return []
                return [fixture]
            else:
                return []
        else:
            return []

    def get_fixture(self, user, domain, location_id):
        """
        Generate a fixture representation of the indicator set. Something like the following:
        <fixture id="indicators:m4change-mobile" user_id="4ce8b1611c38e953d3b3b84dd3a7ac18">
            <monthly-reports>
                <monthly-report startdate="2014-03-01" enddate="2014-03-31" month_year_label="Mar 2014">
                    <facility id="4ce8b1611c38e953d3b3b84dd3a7ac19" name="Facility 1">
                        <report id="facility_anc_hmis_report" name="Facility ANC HMIS Report">
                            <columns>
                                <column name="HMIS Code" />
                                <column name="Data Point" />
                                <column name="Total" />
                            </columns>
                            <rows>
                                <row>
                                    <field value="03" />
                                    <field value="Antenatal Attendance - Total" />
                                    <field value="0" />
                                </row>
                                <!-- ... -->
                            </rows>
                        </report>
                        <!-- ... -->
                    </facility>
                    <!-- ... -->
                </monthly-report>
                <!-- ... -->
            </monthly-reports>
        </fixture>
        """
        def _reports_to_fixture(data, facility_element):
            for report_key in sorted(data):
                columns_added = False
                report_data = data.get(report_key, {})
                report_element = ElementTree.Element('report', attrib={
                    "id": report_key,
                    "name": report_data.name
                })
                columns_element = ElementTree.Element('columns')
                rows_element = ElementTree.Element('rows')

                report_rows = sorted(report_data.rows.items(), key=lambda t: t[1]["hmis_code"]
                                     if t[1].get("hmis_code", None) is not None else t[1].get("s/n"))
                for row in report_rows:
                    row_data = row[1]
                    if not columns_added:
                        for column_key in sorted(row_data):
                            column = ElementTree.Element('column', attrib={
                                'name': column_key
                            })
                            columns_element.append(column)
                        columns_added = True

                    row_element = ElementTree.Element('row', attrib={
                        'hmis_code': str(row_data.get('hmis_code', ''))
                    })
                    for field_key in sorted(row_data):
                        field_element = ElementTree.Element('field', attrib={
                            'value': str(row_data.get(field_key, ''))
                        })
                        row_element.append(field_element)
                    rows_element.append(row_element)

                report_element.append(columns_element)
                report_element.append(rows_element)
                facility_element.append(report_element)
            return facility_element

        def _facility_to_fixture(facility, startdate, enddate):
            facility_id = facility.get_id
            facility_element = ElementTree.Element('facility', attrib={
                'id': facility_id,
                'name': _(facility.name)
            })
            report_data = {}
            m4change_data_source = M4ChangeReportDataSource()
            report_slugs = m4change_data_source.get_report_slugs()
            reports = dict((report.slug, report) for report in m4change_data_source.get_reports())
            for report_slug in report_slugs:
                report_data[report_slug] = FixtureReportResult.by_composite_key(
                    domain.name, facility_id, json_format_date(startdate),
                    json_format_date(enddate), report_slug)
                if report_data[report_slug] is None:
                    name = reports[report_slug].name
                    rows = reports[report_slug].get_initial_row_data()
                    fixture_result = FixtureReportResult(domain=domain.name, location_id=facility_id,
                                                         start_date=startdate, end_date=enddate, report_slug=report_slug,
                                                         rows=rows, name=name)
                    report_data[report_slug] = fixture_result
            facility_element = (_reports_to_fixture(report_data, facility_element))
            return facility_element

        def _month_to_fixture(date_tuple, locations):
            monthly_report_element = ElementTree.Element('monthly-report', attrib={
                'startdate': json_format_date(date_tuple[0]),
                'enddate': json_format_date(date_tuple[1]),
                'month_year_label': date_tuple[0].strftime('%b %Y')
            })

            for location in locations:
                facility_element = _facility_to_fixture(location, date_tuple[0], date_tuple[1])
                if facility_element:
                    monthly_report_element.append(facility_element)
                else:
                    return None
            return monthly_report_element

        root = ElementTree.Element('fixture', attrib={
            'id': self.id,
            'user_id': user._id
        })

        months_element = ElementTree.Element('monthly-reports')

        user_location = Location.get(location_id)
        locations = [user_location] + [descendant for descendant in user_location.descendants]
        dates = get_last_n_months(NUMBER_OF_MONTHS_FOR_FIXTURES)
        for date_tuple in dates:
            monthly_element = _month_to_fixture(date_tuple, locations)
            if monthly_element:
                months_element.append(monthly_element)
            else:
                return None

        root.append(months_element)
        return root

generator = ReportFixtureProvider()
