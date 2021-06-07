import datetime
import requests
from django.http import HttpResponse, HttpResponseBadRequest

from casexml.apps.case.xml.generator import safe_element
from xml.etree import cElementTree as ElementTree


def find_cowin_appointments(request):
    pincode = request.GET.get('pincode')
    on_date = request.GET.get('date')

    error_response = _validate_request(pincode, on_date)
    if error_response:
        return error_response

    response = _get_response(pincode, on_date)
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


def _get_response(pincode, on_date):
    headers = {'Accept-Language': 'en_US'}
    url = "https://cdn-api.co-vin.in/api/v2/appointment/sessions/public/findByPin?" \
          f"pincode={pincode}&date={on_date}"
    return requests.get(url, headers=headers)


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
    appointment_fields = [
        # "center_id",
        "name",
        # "name_l",
        "address",
        # "address_l",
        "state_name",
        # "state_name_l",
        "district_name",
        # "district_name_l",
        "block_name",
        # "block_name_l",
        "pincode",
        # "lat",
        # "long",
        "from",
        "to",
        "fee_type",
        "fee",
        "session_id",
        "date",
        "available_capacity",
        "available_capacity_dose1",
        "available_capacity_dose2",
        "min_age_limit",
        "vaccine",
        "slots"
    ]

    def __init__(self, appointment):
        self.appointment = appointment

    def get_element(self):
        root = safe_element("appointment")
        for field in self.appointment_fields:
            root.append(safe_element(field, self.appointment[field]))
        return root
