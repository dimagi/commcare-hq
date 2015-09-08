import json
from django.core.serializers.json import DjangoJSONEncoder
from casexml.apps.case.xform import cases_referenced_by_xform

from corehq.apps.receiverwrapper.models import FormRepeater, CaseRepeater, ShortFormRepeater, \
    AppStructureRepeater, RegisterGenerator

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

    def get_headers(self, repeat_record, payload_doc):
        return {}


@RegisterGenerator(FormRepeater, 'form_xml', 'XML', is_default=True)
class FormRepeaterXMLPayloadGenerator(BasePayloadGenerator):
    def get_payload(self, repeat_record, payload_doc):
        return payload_doc.get_xml()


@RegisterGenerator(CaseRepeater, 'case_xml', 'XML', is_default=True)
class CaseRepeaterXMLPayloadGenerator(BasePayloadGenerator):
    def get_payload(self, repeat_record, payload_doc):
        return payload_doc.to_xml(self.repeater.version or V2, include_case_on_closed=True)


@RegisterGenerator(CaseRepeater, 'case_json', 'JSON', is_default=False)
class CaseRepeaterJsonPayloadGenerator(BasePayloadGenerator):
    def get_payload(self, repeat_record, payload_doc):
        del payload_doc['actions']
        data = payload_doc.get_json(lite=True)
        return json.dumps(data, cls=DjangoJSONEncoder)


@RegisterGenerator(AppStructureRepeater, "app_structure_xml", "XML", is_default=True)
class AppStructureGenerator(BasePayloadGenerator):
    def get_payload(self, repeat_record, payload_doc):
        # This is the id of the application, currently all we forward
        return repeat_record.payload_id


@RegisterGenerator(ShortFormRepeater, "short_form_json", "Default JSON", is_default=True)
class ShortFormRepeaterXMLPayloadGenerator(BasePayloadGenerator):
    def get_payload(self, repeat_record, form):
        cases = cases_referenced_by_xform(form)
        return json.dumps({'form_id': form._id,
                           'received_on': json_format_datetime(form.received_on),
                           'case_ids': [case._id for case in cases]})
