"""
We use form forwarding to create DHIS2 program events from forms.

Set up form forwarding as follows:

  1. Navigate to Project Settings > Project Administration - Data Forwarding >
     Forward Forms

  2. Click "Add a forwarding location".

  3. Set "URL to forward to" to the DHIS2 API events url. e.g.
     `http://dhis1.internal.commcarehq.org:8080/dhis/api/events.json`

  4. Enable basic authentication and set the username and password.

  5. Choose form format


"""
from datetime import date
import json
from corehq.apps.receiverwrapper.models import RegisterGenerator, FormRepeater
from corehq.apps.receiverwrapper.repeater_generators import BasePayloadGenerator
from custom.dhis2.models import Dhis2Api, json_serializer, Dhis2Settings
from custom.dhis2.const import NUTRITION_ASSESSMENT_EVENT_FIELDS, RISK_ASSESSMENT_EVENT_FIELDS, \
    RISK_ASSESSMENT_PROGRAM_FIELDS


@RegisterGenerator(FormRepeater, 'dhis2_event_json', 'DHIS2 Event JSON')
class FormRepeaterDhis2EventPayloadGenerator(BasePayloadGenerator):

    @staticmethod
    def enabled_for_domain(domain):
        return Dhis2Settings.is_enabled_for_domain(domain)

    def get_headers(self, repeat_record, payload_doc):
        return {'Content-type': 'application/json'}

    def get_payload(self, repeat_record, form):
        if not Dhis2Settings.is_enabled_for_domain(form['domain']):
            return

        from casexml.apps.case.models import CommCareCase  # avoid circular import
        settings = Dhis2Settings.for_domain(form['domain'])
        dhis2_api = Dhis2Api(settings.dhis2.host, settings.dhis2.username, settings.dhis2.password,
                             settings.dhis2.top_org_unit_name)
        if form['xmlns'] == 'http://openrosa.org/formdesigner/b6a45e8c03a6167acefcdb225ee671cbeb332a40':
            # This is a growth monitoring form. It needs to be converted into
            # a paediatric nutrition assessment event.
            nutrition_id = dhis2_api.get_program_id('Paediatric Nutrition Assessment')
            event = dhis2_api.form_to_event(nutrition_id, form, NUTRITION_ASSESSMENT_EVENT_FIELDS)
            # If the form is not to be forwarded, the event will be None
            return json.dumps(event, default=json_serializer) if event else None

        elif form['xmlns'] == 'http://openrosa.org/formdesigner/39F09AD4-B770-491E-9255-C97B34BDD7FC':
            # This is a risk assessment form. It needs to be converted into a
            # risk assessment event.
            risk_id = dhis2_api.get_program_id('Underlying Risk Assessment')
            # Check whether the case needs to be enrolled in the Risk Assessment Program
            cases = CommCareCase.get_by_xform_id(form.get_id)
            if len(cases) != 1:
                # TODO: Fail permanently
                return None
            case = cases[0]
            if not case.get('external_id'):
                # This case has not yet been pushed to DHIS2.
                # TODO: Try again later
                return None
            # TODO: Test one-line alternative below with risk assessment forms
            # Either ...
            if not dhis2_api.enrolled_in(case['external_id'], 'Underlying Risk Assessment'):
                today = date.today().strftime('%Y-%m-%d')
                program_data = {dhis2_attr: case[cchq_attr]
                                for cchq_attr, dhis2_attr in RISK_ASSESSMENT_PROGRAM_FIELDS.iteritems()}
                dhis2_api.enroll_in_id(case['external_id'], risk_id, today, program_data)
            event = dhis2_api.form_to_event(risk_id, form, RISK_ASSESSMENT_EVENT_FIELDS)
            # ... or just ...
            # event = dhis2_api.form_to_event(risk_id, form, RISK_ASSESSMENT_EVENT_FIELDS, case['external_id'])
            # ...?
            return json.dumps(event, default=json_serializer) if event else None

        else:
            # This is not a form we care about
            return None
