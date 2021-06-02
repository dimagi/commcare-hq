import datetime
import requests
from django.http import HttpResponseBadRequest, JsonResponse


def find_appointment_by_pincode(request):
    pincode = request.GET.get('pincode')
    on_date = request.GET.get('date')

    error_response = _validate_request(pincode, on_date)
    if error_response:
        return error_response

    response = _get_response(pincode, on_date)
    return JsonResponse(response.json())


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
