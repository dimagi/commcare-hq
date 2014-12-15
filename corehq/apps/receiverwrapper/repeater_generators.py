import json

from corehq.apps.receiverwrapper.models import FormRepeater, CaseRepeater, ShortFormRepeater, \
    AppStructureRepeater, RegisterGenerator

from casexml.apps.case.models import CommCareCase
from casexml.apps.case.xml import V2

from dimagi.utils.parsing import json_format_datetime


class BasePayloadGenerator(object):

    def __init__(self, repeater):
        self.repeater = repeater

    @staticmethod
    def enabled_for_domain(domain):
        return True

    def get_payload(self, repeat_record, payload_doc):
        raise NotImplementedError()


@RegisterGenerator(FormRepeater, 'form_xml', 'XML', is_default=True)
class FormRepeaterXMLPayloadGenerator(BasePayloadGenerator):
    def get_payload(self, repeat_record, payload_doc):
        return payload_doc.get_xml()


@RegisterGenerator(CaseRepeater, 'case_xml', 'XML', is_default=True)
class CaseRepeaterXMLPayloadGenerator(BasePayloadGenerator):
    def get_payload(self, repeat_record, payload_doc):
        return payload_doc.to_xml(self.repeater.version or V2)


@RegisterGenerator(AppStructureRepeater, "app_structure_xml", "XML", is_default=True)
class AppStructureGenerator(BasePayloadGenerator):
    def get_payload(self, repeat_record, payload_doc):
        # This is the id of the application, currently all we forward
        return repeat_record.payload_id


@RegisterGenerator(ShortFormRepeater, "short_form_json", "Default JSON", is_default=True)
class ShortFormRepeaterXMLPayloadGenerator(BasePayloadGenerator):
    def get_payload(self, repeat_record, form):
        cases = CommCareCase.get_by_xform_id(form.get_id)
        return json.dumps({'form_id': form._id,
                           'received_on': json_format_datetime(form.received_on),
                           'case_ids': [case._id for case in cases]})
