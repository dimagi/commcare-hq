from __future__ import absolute_import
from __future__ import unicode_literals
from corehq.motech.repeaters.repeater_generators import RegisterGenerator, BasePayloadGenerator
from corehq.motech.openmrs.repeaters import (
    RegisterOpenmrsPatientRepeater,
)


class BaseOpenmrsPayloadGenerator(BasePayloadGenerator):
    @property
    def content_type(self):
        return 'application/json'


@RegisterGenerator(RegisterOpenmrsPatientRepeater, 'case_json', 'JSON', is_default=True)
class RegisterOpenmrsPatientPayloadGenerator(BaseOpenmrsPayloadGenerator):
    def get_payload(self, repeat_record, case):
        pass

    def handle_success(self, response, payload_doc, repeat_record):
        pass

    def handle_failure(self, response, payload_doc, repeat_record):
        pass

    def handle_exception(self, exception, repeat_record):
        pass
