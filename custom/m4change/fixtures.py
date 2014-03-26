import calendar
from datetime import datetime

from dateutil.relativedelta import relativedelta
from lxml import etree as ElementTree
from django.utils.translation import ugettext as _

from corehq import Domain
from corehq.apps.commtrack.util import get_commtrack_location_id
from corehq.apps.locations.models import Location
from custom.m4change.constants import M4CHANGE_DOMAINS
from custom.m4change.reports.reports import M4ChangeReportDataSource


def _get_last_n_full_months(months):
    ranges = []
    today = datetime.utcnow()
    for month in range(1, months + 1):
        month_start = datetime(today.year, today.month, 1) - relativedelta(months=month)
        last_day_of_month = calendar.monthrange(month_start.year, month_start.month)[1]
        month_end = datetime(month_start.year, month_start.month, last_day_of_month)
        ranges.insert(0, (month_start, month_end))
    return ranges


def generator(user, version, last_sync):
    if user.domain in M4CHANGE_DOMAINS:
        domain = Domain.get_by_name(user.domain)
        location_id = get_commtrack_location_id(user, domain)
        if location_id is not None:
            return [ReportFixtureProvider('reports:m4change-mobile', user, domain, location_id).to_fixture()]
        else:
            return []
    else:
        return []


class ReportFixtureProvider(object):

    def __init__(self, id, user, domain, location_id):
        self.id = id
        self.user = user
        self.dates = _get_last_n_full_months(2)
        self.domain = domain
        self.location_id = location_id

    def to_fixture(self):
        """
        Generate a fixture representation of the indicator set. Something like the following:
        <fixture id="indicators:m4change-mobile" user_id="4ce8b1611c38e953d3b3b84dd3a7ac18">
            <monthly-report startdate="2013-02-01" enddate="2013-03-01">
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
        </fixture>
        """
        def _reports_to_fixture(report_data, facility_id, facility_element):
            for dictionary in sorted(report_data):
                columns_added = False
                for report_key in sorted(dictionary):
                    data = dictionary.get(report_key, {})
                    name = data.get('name', None)
                    report_element = ElementTree.Element('report', attrib={
                        'id': report_key,
                        'name': name
                    })
                    columns_element = ElementTree.Element('columns')
                    rows_element = ElementTree.Element('rows')

                    report_rows = data.get('data', {})
                    for row_key in sorted(report_rows):
                        row_data = report_rows.get(row_key, {})
                        if not columns_added:
                            for column_key in sorted(row_data):
                                column = ElementTree.Element('column', attrib={
                                    'name': column_key
                                })
                                columns_element.append(column)
                            columns_added = True

                        row_element = ElementTree.Element('row')
                        for field_key in sorted(row_data):
                            field_element = ElementTree.Element('field', attrib={
                                'value': str(row_data.get(field_key, ''))
                            })
                            row_element.append(field_element)
                        rows_element.append(row_element)

                    report_element.append(columns_element)
                    report_element.append(rows_element)
                    return report_element

        def _facility_to_fixture(facility, startdate, enddate):
            facility_id = facility.get_id
            facility_element = ElementTree.Element('facility', attrib={
                'id': facility_id,
                'name': _(facility.name)
            })
            report_data = M4ChangeReportDataSource(config={
                'startdate': startdate,
                'enddate': enddate,
                'location_id': facility_id,
                'domain': self.domain.name
            }).get_data()
            facility_element.append(_reports_to_fixture(report_data, facility_id, facility_element))
            return facility_element

        def _month_to_fixture(date_tuple, locations):
            monthly_report_element = ElementTree.Element('monthly-report', attrib={
                'startdate': date_tuple[0].strftime('%Y-%m-%d'),
                'enddate': date_tuple[1].strftime('%Y-%m-%d')
            })
            for location in locations:
                monthly_report_element.append(_facility_to_fixture(location, date_tuple[0], date_tuple[1]))
            return monthly_report_element

        root = ElementTree.Element('fixture', attrib={
            'id': self.id,
            'user_id': self.user._id
        })

        user_location = Location.get(self.location_id)
        locations =  [user_location] + [descendant for descendant in user_location.descendants]
        for date_tuple in self.dates:
            root.append(_month_to_fixture(date_tuple, locations))
        return root

    def to_string(self):
        return ElementTree.tostring(self.to_fixture(), encoding="utf-8")
