import json

from django.core.serializers.json import DjangoJSONEncoder

from corehq.apps.userreports.specs import EvaluationContext
from corehq.motech.repeaters.repeater_generators import BasePayloadGenerator


class ExpressionPayloadGenerator(BasePayloadGenerator):
    @property
    def content_type(self):
        return 'application/json'

    def get_payload(self, repeat_record, payload_doc, parsed_expression):
        result = parsed_expression(payload_doc, EvaluationContext(payload_doc))
        return json.dumps(result, cls=DjangoJSONEncoder)
