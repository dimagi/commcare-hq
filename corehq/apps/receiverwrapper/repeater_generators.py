from corehq.apps.receiverwrapper.models import FormRepeater, CaseRepeater, ShortFormRepeater, AppStructureRepeater, \
    RegisterGeneratorDecorator
from dimagi.utils.decorators.memoized import memoized


class BasePayloadGenerator(object):

    def __init__(self, repeater):
        self.repeater = repeater

    @staticmethod
    def enabled_for_domain(domain):
        return True

    def get_payload(self, repeat_record):
        raise NotImplementedError()


@RegisterGeneratorDecorator(repeater_cls=FormRepeater, format='XML', label='Default XML')
class FormRepeaterXMLPayloadGenerator(BasePayloadGenerator):
    def get_payload(self, repeat_record):
        return XFormInstance.get(repeat_record.payload_id).get_xml()


@RegisterGeneratorDecorator(repeater_cls=CaseRepeater, format='XML', label='Default XML')
class CaseRepeaterXMLPayloadGenerator(BasePayloadGenerator):
    def get_payload(self, repeat_record):
        return self.repeater._payload_doc(repeat_record).to_xml(version=self.repeater.version or V2)


@RegisterGeneratorDecorator(repeater_cls=AppStructureRepeater, format="XML", label="Default XML")
class AppStructureGenerator(BasePayloadGenerator):
    def get_payload(self, repeat_record):
        # This is the id of the application, currently all we forward
        return repeat_record.payload_id


@RegisterGeneratorDecorator(repeater_cls=ShortFormRepeater, format="XML", label="Default XML")
class ShortFormRepeaterXMLPayloadGenerator(BasePayloadGenerator):
    def get_payload(self, repeat_record):
        form = self.repeater._payload_doc(repeat_record)
        cases = CommCareCase.get_by_xform_id(form.get_id)
        return json.dumps({'form_id': form._id,
                           'received_on': json_format_datetime(form.received_on),
                           'case_ids': [case._id for case in cases]})
