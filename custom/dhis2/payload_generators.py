"""
We use form forwarding to create DHIS2 program events from forms.

Set up form forwarding as follows:

  1. Navigate to "Project Settings" > "Project Administration":
     "Data Forwarding" > "Forward Forms"

  2. Click "Add a forwarding location".

  3. Set "URL to forward to" to the DHIS2 API events url. e.g.
     `http://dhis1.internal.commcarehq.org:8080/dhis/api/events.json`

  4. Enable basic authentication and set "Username" and "Password".

  5. Set "Payload Format" to "DHIS2 Event JSON"

  6. Click "Start Forwarding"


"""
from datetime import date
import json
import logging
from corehq.apps.receiverwrapper.exceptions import IgnoreDocument
from corehq.apps.receiverwrapper.models import RegisterGenerator, FormRepeater
from corehq.apps.receiverwrapper.repeater_generators import BasePayloadGenerator
from custom.dhis2.models import Dhis2Api, json_serializer, Dhis2Settings
from custom.dhis2.const import NUTRITION_ASSESSMENT_EVENT_FIELDS, RISK_ASSESSMENT_EVENT_FIELDS, \
    RISK_ASSESSMENT_PROGRAM_FIELDS, REGISTER_CHILD_XMLNS, GROWTH_MONITORING_XMLNS, RISK_ASSESSMENT_XMLNS, \
    NUTRITION_ASSESSMENT_PROGRAM_FIELDS, CASE_TYPE
from custom.dhis2.tasks import push_case
from dimagi.utils.parsing import json_format_date


logger = logging.getLogger(__name__)


@RegisterGenerator(FormRepeater, 'dhis2_event_json', 'DHIS2 Event JSON')
class FormRepeaterDhis2EventPayloadGenerator(BasePayloadGenerator):

    @staticmethod
    def enabled_for_domain(domain):
        return Dhis2Settings.is_enabled_for_domain(domain)

    def get_headers(self, repeat_record, payload_doc):
        return {'Content-type': 'application/json'}

    def _update_instance(self, dhis2_api, case):
        instance = dhis2_api.get_te_inst(case['external_id'])
        instance.update({dhis2_attr: case[cchq_attr]
                         for cchq_attr, dhis2_attr in NUTRITION_ASSESSMENT_PROGRAM_FIELDS.iteritems()
                         if getattr(case, cchq_attr, None)})
        if 'Gender' in instance:
            instance['Gender'] = instance['Gender'].capitalize()
        dhis2_api.update_te_inst(instance)

    def get_payload(self, repeat_record, form):
        from casexml.apps.case.xform import cases_referenced_by_xform

        logger.debug('DHIS2: Form domain "%s" XMLNS "%s"', form['domain'], form['xmlns'])
        if form['xmlns'] not in (REGISTER_CHILD_XMLNS, GROWTH_MONITORING_XMLNS, RISK_ASSESSMENT_XMLNS):
            # This is not a form we care about
            raise IgnoreDocument


        settings = Dhis2Settings.for_domain(form['domain'])
        dhis2_api = Dhis2Api(settings.dhis2['host'], settings.dhis2['username'], settings.dhis2['password'],
                             settings.dhis2['top_org_unit_name'])
        cases = cases_referenced_by_xform(form)
        case = next(c for c in cases if c.type == CASE_TYPE)
        event = None

        if form['xmlns'] == REGISTER_CHILD_XMLNS:
            # Create a DHIS2 tracked entity instance from the form's case and
            # enroll in the nutrition assessment programme.
            logger.debug('DHIS2: Processing Register Child form')
            push_case(case, dhis2_api)
            #  We just need to enroll. No event to create
            raise IgnoreDocument

        elif form['xmlns'] == GROWTH_MONITORING_XMLNS:
            logger.debug('DHIS2: Processing Growth Monitoring form')
            if not getattr(case, 'external_id', None):
                logger.info('Register Child form must be processed before Growth Monitoring form')
                return  # Try again later
            self._update_instance(dhis2_api, case)
            # Create a paediatric nutrition assessment event.
            program_id = dhis2_api.get_program_id('Paediatric Nutrition Assessment')
            program_stage_id = dhis2_api.get_program_stage_id('Nutrition Assessment')
            event = dhis2_api.form_to_event(program_id, form, NUTRITION_ASSESSMENT_EVENT_FIELDS, program_stage_id,
                                            case['external_id'])

        elif form['xmlns'] == RISK_ASSESSMENT_XMLNS:
            logger.debug('DHIS2: Processing Risk Assessment form')
            if not getattr(case, 'external_id', None):
                logger.info('Register Child form must be processed before Risk Assessment form')
                return  # Try again later
            self._update_instance(dhis2_api, case)
            # Check whether the case needs to be enrolled in the Risk Assessment Program
            program_id = dhis2_api.get_program_id('Underlying Risk Assessment')
            if not dhis2_api.enrolled_in(case['external_id'], 'Underlying Risk Assessment'):
                today = json_format_date(date.today())
                program_data = {dhis2_attr: case[cchq_attr]
                                for cchq_attr, dhis2_attr in RISK_ASSESSMENT_PROGRAM_FIELDS.iteritems()}
                dhis2_api.enroll_in_id(case['external_id'], program_id, today, program_data)
            # Create a risk assessment event.
            program_stage_id = dhis2_api.get_program_stage_id('Underlying Risk Assessment')
            event = dhis2_api.form_to_event(program_id, form, RISK_ASSESSMENT_EVENT_FIELDS, program_stage_id,
                                            case['external_id'])

        return json.dumps(event, default=json_serializer)
