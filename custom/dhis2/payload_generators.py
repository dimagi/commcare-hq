from datetime import date
import json
from casexml.apps.case.models import CommCareCase
from corehq.apps.receiverwrapper.models import FormRepeater, RegisterGenerator
from corehq.apps.receiverwrapper.repeater_generators import BasePayloadGenerator
from custom.dhis2.models import Dhis2Api
from custom.dhis2.tasks import NUTRITION_ASSESSMENT_EVENT_FIELDS, RISK_ASSESSMENT_EVENT_FIELDS, \
    RISK_ASSESSMENT_PROGRAM_FIELDS
from django.conf import settings
from custom.dhis2.tasks import DOMAIN


@RegisterGenerator(FormRepeater, 'dhis2_nutrition_assessment_event_json', 'DHIS2 Nutrition Assessment JSON')
class FormRepeaterDhis2NutritionAssessmentEventPayloadGenerator(BasePayloadGenerator):

    @staticmethod
    def enabled_for_domain(domain):
        return domain == DOMAIN

    def get_payload(self, repeat_record, form):
        if form['xmlns'] != 'http://openrosa.org/formdesigner/b6a45e8c03a6167acefcdb225ee671cbeb332a40':
            # This is not a growth monitoring form. Only growth monitoring forms
            # can be converted into paediatric nutrition assessment events.
            # TODO: Skip and don't try again
            return json.dumps(None)
        dhis2_api = Dhis2Api(settings.DHIS2_HOST, settings.DHIS2_USERNAME, settings.DHIS2_PASSWORD)
        nutrition_id = dhis2_api.get_program_id('Pediatric Nutrition Assessment')
        event = dhis2_api.form_to_event(nutrition_id, form, NUTRITION_ASSESSMENT_EVENT_FIELDS)
        return json.dumps(event)


@RegisterGenerator(FormRepeater, 'dhis2_risk_assessment_event_json', 'DHIS2 Risk Assessment JSON')
class FormRepeaterDhis2RiskAssessmentEventPayloadGenerator(BasePayloadGenerator):

    @staticmethod
    def enabled_for_domain(domain):
        return domain == DOMAIN

    def get_payload(self, repeat_record, form):
        if form['xmlns'] != 'http://openrosa.org/formdesigner/39F09AD4-B770-491E-9255-C97B34BDD7FC':
            # This form cannot be converted into a risk assessment event
            # TODO: Skip and don't try again
            return json.dumps(None)
        dhis2_api = Dhis2Api(settings.DHIS2_HOST, settings.DHIS2_USERNAME, settings.DHIS2_PASSWORD)
        risk_id = dhis2_api.get_program_id('Underlying Risk Assessment')
        # Check whether the case needs to be enrolled in the Risk Assessment Program
        cases = CommCareCase.get_by_xform_id(form.get_id)
        if len(cases) != 1:
            # TODO: Fail permanently
            return json.dumps(None)
        case = cases[0]
        if not case.get('external_id'):
            # This case has not yet been pushed to DHIS2.
            # TODO: Try again tomorrow
            return json.dumps(None)
        if not dhis2_api.enrolled_in(case['external_id'], 'Underlying Risk Assessment'):
            today = date.today().strftime('%Y-%m-%d')
            program_data = {dhis2_attr: case[cchq_attr]
                            for cchq_attr, dhis2_attr in RISK_ASSESSMENT_PROGRAM_FIELDS.iteritems()}
            dhis2_api.enroll_in_id(case['external_id'], risk_id, today, program_data)
        event = dhis2_api.form_to_event(risk_id, form, RISK_ASSESSMENT_EVENT_FIELDS)
        return json.dumps(event)
