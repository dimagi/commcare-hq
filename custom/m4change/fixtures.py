import calendar
from datetime import datetime

from dateutil.relativedelta import relativedelta
from lxml import etree as ElementTree
from django.utils.translation import ugettext as _

from corehq import Domain
from corehq.apps.commtrack.util import get_commtrack_location_id
from corehq.apps.locations.models import Location
from custom.m4change.constants import M4CHANGE_DOMAINS, NUMBER_OF_MONTHS_FOR_FIXTURES
from custom.m4change.models import FixtureReportResult
from custom.m4change.reports.reports import M4ChangeReportDataSource


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

def generator(user, version, last_sync):
    if user.domain in M4CHANGE_DOMAINS:
        domain = Domain.get_by_name(user.domain)
        location_id = get_commtrack_location_id(user, domain)
        if location_id is not None:
            fixture = ReportFixtureProvider('reports:m4change-mobile', user, domain, location_id).to_fixture()
            if fixture is None:
                return []
            return [fixture]
        else:
            return []
    else:
        return []


class ReportFixtureProvider(object):

    def __init__(self, id, user, domain, location_id):
        self.id = id
        self.user = user
        self.dates = get_last_n_months(NUMBER_OF_MONTHS_FOR_FIXTURES)
        self.domain = domain
        self.location_id = location_id

    def to_fixture(self):
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
                    'id': report_key,
                    'name': report_data.name
                })
                columns_element = ElementTree.Element('columns')
                rows_element = ElementTree.Element('rows')

                report_rows = report_data.rows
                for row_key in sorted(report_rows):
                    row_data = report_rows.get(row_key, {})
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
            report_slugs = M4ChangeReportDataSource().get_report_slugs()
            report_data = {}
            startdate = startdate.strftime("%Y-%m-%d")
            enddate = enddate.strftime("%Y-%m-%d")
            for report_slug in report_slugs:
                report_data[report_slug] = FixtureReportResult.by_composite_key(self.domain.name, facility_id, startdate,
                                                                                enddate, report_slug)
            if None in report_data.values():
                return None
            facility_element = (_reports_to_fixture(report_data, facility_element))
            return facility_element

        def _month_to_fixture(date_tuple, locations):
            monthly_report_element = ElementTree.Element('monthly-report', attrib={
                'startdate': date_tuple[0].strftime('%Y-%m-%d'),
                'enddate': date_tuple[1].strftime('%Y-%m-%d'),
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
            'user_id': self.user._id
        })

        months_element = ElementTree.Element('monthly-reports')

        user_location = Location.get(self.location_id)
        locations = [user_location] + [descendant for descendant in user_location.descendants]
        for date_tuple in self.dates:
            monthly_element = _month_to_fixture(date_tuple, locations)
            if monthly_element:
                months_element.append(monthly_element)
            else:
                return None

        root.append(months_element)
        return root

    def to_string(self):
        return ElementTree.tostring(self.to_fixture(), encoding="utf-8")
