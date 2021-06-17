import datetime
from xml.etree import cElementTree as ElementTree

from django.http import HttpResponse, HttpResponseBadRequest

from casexml.apps.case.xml.generator import safe_element

from corehq.apps.cowin.api import (
    send_request_to_get_available_appointments_via_public_api,
)


def find_cowin_appointments(request):
    pincode = request.GET.get('pincode')
    on_date = request.GET.get('date')

    error_response = _validate_request(pincode, on_date)
    if error_response:
        return error_response

    response = send_request_to_get_available_appointments_via_public_api(pincode, on_date)
    appointments = response.json()['sessions']
    fixtures = AppointmentResultsFixture(appointments).fixture
    return HttpResponse(fixtures, content_type="text/xml; charset=utf-8")


def _validate_request(pincode, on_date):
    if not pincode or not on_date:
        return HttpResponseBadRequest("please provide both pincode and a date")

    try:
        datetime.datetime.strptime(on_date, '%d-%m-%Y')
    except ValueError:
        return HttpResponseBadRequest("Invalid date, format should be DD-MM-YYYY")


class AppointmentResultsFixture(object):
    id = "appointments"

    def __init__(self, appointments):
        self.appointments = appointments

    @property
    def fixture(self):
        element = safe_element("results")
        element.set('id', self.id)

        for appointment in self.appointments:
            element.append(AppointmentResultXMLGenerator(appointment).get_element())

        return ElementTree.tostring(element, encoding='utf-8')


class AppointmentResultXMLGenerator(object):
    appointment_fields = {
        # "center_id",
        "name": "Name",
        # "name_l",
        "address": "Address",
        # "address_l",
        "state_name": "State",
        # "state_name_l",
        "district_name": "District",
        # "district_name_l",
        "block_name": "Block",
        # "block_name_l",
        "pincode": "Pincode",
        # "lat",
        # "long",
        "from": "From",
        "to": "To",
        "fee_type": "Fee Type",
        "fee": "Fee",
        "session_id": "Session ID",
        "date": "Date",
        "available_capacity": "Capacity",
        "available_capacity_dose1": "First Dose",
        "available_capacity_dose2": "Second Dose",
        "min_age_limit": "Minimum Age",
        "vaccine": "Vaccine",
        "slots": "Slots"
    }

    def __init__(self, appointment):
        self.appointment = appointment

    def get_element(self):
        root = safe_element("appointment")
        for field in self.appointment_fields:
            root.append(safe_element(field, self.appointment[field]))
        return root
