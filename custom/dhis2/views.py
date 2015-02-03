"""
DHIS2 Integration uses a web service to send form data to DHIS2 in order to
create DHIS2 program events.

These are essentially callbacks for FormRepeater.

We need separate views because FormRepeater will only send a request with its
form data. But to create a DHIS2 event we will also need to know which fields
to send, the DHIS2 equivalents of those fields, and which kind of event to
create for each kind of form.
"""
from datetime import date
import json
from apps.case.models import CommCareCase
from custom.dhis2.models import Dhis2Api
from custom.dhis2.tasks import NUTRITION_ASSESSMENT_FIELDS, RISK_ASSESSMENT_FIELDS
from django.conf import settings
from django.http import HttpResponse


def post_event(request):
    """
    Pass the event received in request.POST through to DHIS2
    """
    dhis2_api = Dhis2Api(settings.DHIS2_HOST, settings.DHIS2_USERNAME, settings.DHIS2_PASSWORD)
    event = json.loads(request.POST)
    dhis2_api.send_events(event)


def post_nutrition_assessment_event(request):
    """
    Create a nutrition assessment event
    """
    dhis2_api = Dhis2Api(settings.DHIS2_HOST, settings.DHIS2_USERNAME, settings.DHIS2_PASSWORD)
    nutrition_id = dhis2_api.get_program_id('Pediatric Nutrition Assessment')
    event = dhis2_api.form_to_event(nutrition_id, request.POST, NUTRITION_ASSESSMENT_FIELDS)
    dhis2_api.send_events(event)
    return HttpResponse('Created', status_code=201)


def post_risk_assessment_event(request):
    """
    Enroll the case in the risk assessment program if necessary, and create a
    risk assessment event
    """
    dhis2_api = Dhis2Api(settings.DHIS2_HOST, settings.DHIS2_USERNAME, settings.DHIS2_PASSWORD)
    today = date.today().strftime('%Y-%m-%d')
    risk_id = dhis2_api.get_program_id('Underlying Risk Assessment')

    # Check whether the case needs to be enrolled in the Risk Assessment Program
    cases = CommCareCase.get_by_xform_id(request.POST['_id'])
    if len(cases) != 1:
        # TODO: Do something
        pass
    case = cases[0]
    # TODO: Will external ID be set?
    if not dhis2_api.enrolled_in(case['external_id'], 'Child', 'Underlying Risk Assessment'):
        today = date.today().strftime('%Y-%m-%d')
        program_data = {
            'Household Number': case['mother_id'],
            'Name of Mother/Guardian': case['mother_first_name'],
            'GN Division of Household': case['gn'],
        }
        # TODO: Will external ID be set?
        dhis2_api.enroll_in_id(case['external_id'], risk_id, today, program_data)

    event = dhis2_api.form_to_event(risk_id, request.POST, RISK_ASSESSMENT_FIELDS)
    dhis2_api.send_events(event)
    return HttpResponse('Created', status_code=201)
