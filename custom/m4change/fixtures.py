from lxml import etree as ElementTree
from datetime import timedelta

from django.utils import translation
from django.utils.datetime_safe import datetime
from django.utils.translation import ugettext as _

from corehq.apps.locations.models import Location
from corehq.apps.users.models import CommCareUser
from custom.m4change.constants import M4CHANGE_DOMAINS
from custom.m4change.reports.reports import M4ChangeReportDataSource


def generator(user, version, last_sync):
    from reports.anc_hmis_report import AncHmisReport
    hard_coded_reports = [
        AncHmisReport,
    ]

    if user.domain in M4CHANGE_DOMAINS:
        startdate = datetime.utcnow().today() - timedelta(days=30)
        enddate = datetime.utcnow().today()
        return ReportFixtureProvider('reports:m4change-mobile', user, hard_coded_reports, startdate, enddate).to_fixture()
    else:
        return []


class ReportFixtureProvider(object):

    def __init__(self, id, user, reports, startdate, enddate):
        self.id = id
        self.user = user
        self.reports = reports
        self.startdate = startdate
        self.enddate = enddate

    def to_fixture(self):
        """
        Generate a fixture representation of the indicator set. Something like the following:
        <fixture id="indicators:m4change-mobile" user_id="4ce8b1611c38e953d3b3b84dd3a7ac18" startdate="2013-02-01" enddate="2013-03-01">
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
                    facility_element.append(report_element)

        def _facility_to_fixture(facility):
            facility_id = facility.get_id
            facility_element = ElementTree.Element('facility', attrib={
                'id': facility_id,
                'name': _(facility.name)
            })
            report_data = M4ChangeReportDataSource(config={
                'startdate': self.startdate,
                'enddate': self.enddate,
                'location_id': self.user.get_domain_membership(DOMAIN).location_id
            }).get_data()
            _reports_to_fixture(report_data, facility_id, facility_element)
            return facility_element

        root = ElementTree.Element('fixture', attrib={
            'user_id': self.user._id,
            'startdate': self.startdate.strftime('%Y-%m-%d'),
            'enddate': self.enddate.strftime('%Y-%m-%d')
        })

        user_location = Location.get(self.user.get_domain_membership(DOMAIN).location_id)
        locations =  [user_location] + [descendant for descendant in user_location.descendants]
        for location in locations:
            root.append(_facility_to_fixture(location))
        return root

    def to_string(self):
        return ElementTree.tostring(self.to_fixture(), encoding="utf-8")
