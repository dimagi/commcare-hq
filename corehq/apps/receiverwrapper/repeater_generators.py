from corehq.apps.receiverwrapper.models import FormRepeater, CaseRepeater, ShortFormRepeater, \
    AppStructureRepeater, RegisterGeneratorDecorator
from couchforms.models import XFormInstance
from dimagi.utils.decorators.memoized import memoized



class BasePayloadGenerator(object):

    def __init__(self, repeater):
        self.repeater = repeater

    @staticmethod
    def enabled_for_domain(domain):
        return True

    def get_payload(self, repeat_record):
        raise NotImplementedError()


@RegisterGeneratorDecorator(FormRepeater, 'form_xml', 'Default XML', is_default=True)
class FormRepeaterXMLPayloadGenerator(BasePayloadGenerator):
    def get_payload(self, repeat_record):
        return self.repeater._payload_doc(repeat_record).get_xml()


@RegisterGeneratorDecorator(CaseRepeater, 'case_xml', 'Default XML', is_default=True)
class CaseRepeaterXMLPayloadGenerator(BasePayloadGenerator):
    def get_payload(self, repeat_record):
        return self.repeater._payload_doc(repeat_record).to_xml(self.repeater.version or V2)


@RegisterGeneratorDecorator(AppStructureRepeater, "app_structure_xml", "Default XML", is_default=True)
class AppStructureGenerator(BasePayloadGenerator):
    def get_payload(self, repeat_record):
        # This is the id of the application, currently all we forward
        return repeat_record.payload_id


@RegisterGeneratorDecorator(ShortFormRepeater, "short_form_json", "Default JSON", is_default=True)
class ShortFormRepeaterXMLPayloadGenerator(BasePayloadGenerator):
    def get_payload(self, repeat_record):
        form = self.repeater._payload_doc(repeat_record)
        cases = CommCareCase.get_by_xform_id(form.get_id)
        return json.dumps({'form_id': form._id,
                           'received_on': json_format_datetime(form.received_on),
                           'case_ids': [case._id for case in cases]})
