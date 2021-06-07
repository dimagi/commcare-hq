from django.test import SimpleTestCase

from corehq.apps.app_manager.tests.util import TestXmlMixin
from corehq.apps.cowin.views import AppointmentResultsFixture

DUMMY_RESPONSE = {
    "sessions": [{
        "center_id": 1234,
        "name": "District General Hostpital",
        "name_l": "",
        "address": "45 M G Road",
        "address_l": "",
        "state_name": "Maharashtra",
        "state_name_l": "",
        "district_name": "Satara",
        "district_name_l": "",
        "block_name": "Jaoli",
        "block_name_l": "",
        "pincode": "413608",
        "lat": 28.7,
        "long": 77.1,
        "from": "09:00:00",
        "to": "18:00:00",
        "fee_type": "Paid",
        "fee": "250",
        "session_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
        "date": "31-05-2021",
        "available_capacity": 50,
        "available_capacity_dose1": 25,
        "available_capacity_dose2": 25,
        "min_age_limit": 18,
        "vaccine": "COVISHIELD",
        "slots": [
            "FORENOON",
            "AFTERNOON"
        ]
    }]
}


class TestAppointmentResultsFixture(SimpleTestCase, TestXmlMixin):
    def test_fixture(self):
        fixture = AppointmentResultsFixture(DUMMY_RESPONSE['sessions']).fixture
        self.assertXmlPartialEqual(
            """
            <partial>
              <results id="appointments">
                <appointment>
                  <name>District General Hostpital</name>
                  <address>45 M G Road</address>
                  <state_name>Maharashtra</state_name>
                  <district_name>Satara</district_name>
                  <block_name>Jaoli</block_name>
                  <pincode>413608</pincode>
                  <from>09:00:00</from>
                  <to>18:00:00</to>
                  <fee_type>Paid</fee_type>
                  <fee>250</fee>
                  <session_id>3fa85f64-5717-4562-b3fc-2c963f66afa6</session_id>
                  <date>31-05-2021</date>
                  <available_capacity>50</available_capacity>
                  <available_capacity_dose1>25</available_capacity_dose1>
                  <available_capacity_dose2>25</available_capacity_dose2>
                  <min_age_limit>18</min_age_limit>
                  <vaccine>COVISHIELD</vaccine>
                  <slots>[\'FORENOON\', \'AFTERNOON\']</slots>
                </appointment>
              </results>
            </partial>
            """,
            fixture,
            "."
        )
