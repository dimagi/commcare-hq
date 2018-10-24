from __future__ import absolute_import
from __future__ import unicode_literals

from django.http import JsonResponse
from django.views.generic import View


class OData(View):
    urlname = 'odata'

    def get(self, request):
        return JsonResponse(
            {
                "@odata.context": "http://services.odata.org/V4/(S(2znladk1vf0nzrxyd2uhrjw4))/TripPinServiceRW/$metadata#People",
                "value": [{
                    "@odata.id": "http://services.odata.org/V4/(S(2znladk1vf0nzrxyd2uhrjw4))/TripPinServiceRW/People('sandyosborn')",
                    "@odata.etag": "W/\"08D6389C62969DAE\"",
                    "@odata.editLink": "http://services.odata.org/V4/(S(2znladk1vf0nzrxyd2uhrjw4))/TripPinServiceRW/People('sandyosborn')",
                    "UserName": "sandyosborn", "FirstName": "Sandy", "LastName": "Osborn",
                    "Emails": ["Sandy@example.com", "Sandy@contoso.com"], "AddressInfo": [],
                    "Gender": "Female", "Concurrency": 636758641639595438}, {
                    "@odata.id": "http://services.odata.org/V4/(S(2znladk1vf0nzrxyd2uhrjw4))/TripPinServiceRW/People('ursulabright')",
                    "@odata.etag": "W/\"08D6389C62969DAE\"",
                    "@odata.editLink": "http://services.odata.org/V4/(S(2znladk1vf0nzrxyd2uhrjw4))/TripPinServiceRW/People('ursulabright')",
                    "UserName": "ursulabright", "FirstName": "Ursula", "LastName": "Bright",
                    "Emails": ["Ursula@example.com", "Ursula@contoso.com"], "AddressInfo": [],
                    "Gender": "Female", "Concurrency": 636758641639595438}, {
                    "@odata.id": "http://services.odata.org/V4/(S(2znladk1vf0nzrxyd2uhrjw4))/TripPinServiceRW/People('genevievereeves')",
                    "@odata.etag": "W/\"08D6389C62969DAE\"",
                    "@odata.editLink": "http://services.odata.org/V4/(S(2znladk1vf0nzrxyd2uhrjw4))/TripPinServiceRW/People('genevievereeves')",
                    "UserName": "genevievereeves", "FirstName": "Genevieve", "LastName": "Reeves",
                    "Emails": ["Genevieve@example.com", "Genevieve@contoso.com"], "AddressInfo": [],
                    "Gender": "Female", "Concurrency": 636758641639595438}, {
                    "@odata.id": "http://services.odata.org/V4/(S(2znladk1vf0nzrxyd2uhrjw4))/TripPinServiceRW/People('kristakemp')",
                    "@odata.etag": "W/\"08D6389C62969DAE\"",
                    "@odata.editLink": "http://services.odata.org/V4/(S(2znladk1vf0nzrxyd2uhrjw4))/TripPinServiceRW/People('kristakemp')",
                    "UserName": "kristakemp", "FirstName": "Krista", "LastName": "Kemp",
                    "Emails": ["Krista@example.com"], "AddressInfo": [], "Gender": "Female",
                    "Concurrency": 636758641639595438}]
            }
        )