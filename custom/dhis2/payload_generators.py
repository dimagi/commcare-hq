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
from casexml.apps.case.models import CommCareCase
from corehq.apps.receiverwrapper.models import FormRepeater, RegisterGenerator, Repeater, register_repeater_type
from corehq.apps.receiverwrapper.repeater_generators import BasePayloadGenerator
from corehq.apps.receiverwrapper.signals import create_repeat_records, successful_form_received
from custom.dhis2.models import Dhis2Api, json_serializer
from custom.dhis2.tasks import NUTRITION_ASSESSMENT_EVENT_FIELDS, RISK_ASSESSMENT_EVENT_FIELDS, \
    RISK_ASSESSMENT_PROGRAM_FIELDS
from custom.dhis2.tasks import DOMAIN
from dimagi.utils.decorators.memoized import memoized
from django.conf import settings
from couchforms.models import XFormInstance


# @register_repeater_type
# class JsonFormRepeater(FormRepeater):
#
#     def __unicode__(self):
#         return "forwarding forms to external JSON API: %s" % self.url
#
#     def get_headers(self, repeat_record):
#         """
#         Adds the correct content type to the HTTP request headers
#         """
#         headers = super(JsonFormRepeater, self)
#         headers['Content-type'] = 'application/json'
#         return headers
#
#     def get_url(self, repeat_record):
#         """
#         The parent class adds app_id to the URL params. Avoid that.
#         """
#         return Repeater.get_url(self, repeat_record)
#
#     @memoized
#     def payload_doc(self, repeat_record):
#         return XFormInstance.get(repeat_record.payload_id)
#
#
# def create_json_form_repeat_records(sender, xform, **kwargs):
#     create_repeat_records(JsonFormRepeater, xform)
#
#
# successful_form_received.connect(create_json_form_repeat_records)


@RegisterGenerator(FormRepeater, 'dhis2_event_json', 'DHIS2 Event JSON')
class FormRepeaterDhis2EventPayloadGenerator(BasePayloadGenerator):

    @staticmethod
    def enabled_for_domain(domain):
        return domain == DOMAIN

    def get_payload(self, repeat_record, form):
        if form['xmlns'] == 'http://openrosa.org/formdesigner/b6a45e8c03a6167acefcdb225ee671cbeb332a40':
            # This is a growth monitoring form. It needs to be converted into
            # a paediatric nutrition assessment event.
            dhis2_api = Dhis2Api(settings.DHIS2_HOST, settings.DHIS2_USERNAME, settings.DHIS2_PASSWORD)
            nutrition_id = dhis2_api.get_program_id('Paediatric Nutrition Assessment')
            event = dhis2_api.form_to_event(nutrition_id, form, NUTRITION_ASSESSMENT_EVENT_FIELDS)
            return json.dumps(event, default=json_serializer)

        elif form['xmlns'] == 'http://openrosa.org/formdesigner/39F09AD4-B770-491E-9255-C97B34BDD7FC':
            # This is a risk assessment form. It needs to be converted into a
            # risk assessment event.
            dhis2_api = Dhis2Api(settings.DHIS2_HOST, settings.DHIS2_USERNAME, settings.DHIS2_PASSWORD)
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
            return json.dumps(event, default=json_serializer)

        else:
            # This is not a form we care about
            return None
