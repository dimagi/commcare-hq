import json

from datetime import datetime
from uuid import uuid4

from django.core.serializers.json import DjangoJSONEncoder
from casexml.apps.case.xform import cases_referenced_by_xform

from corehq.apps.repeaters.models import FormRepeater, CaseRepeater, ShortFormRepeater, \
    AppStructureRepeater, RegisterGenerator

from casexml.apps.case.xml import V2

from dimagi.utils.parsing import json_format_datetime


def _get_test_form():
    from corehq.form_processor.tests.utils import TestFormMetadata
    from corehq.form_processor.tests.utils import get_simple_wrapped_form
    metadata = TestFormMetadata(domain='demo-domain', xmlns=uuid4().hex, form_name='Demo Form')
    return get_simple_wrapped_form('test-form-' + uuid4().hex, metadata=metadata, save=False)


class BasePayloadGenerator(object):

    def __init__(self, repeater):
        self.repeater = repeater

    @staticmethod
    def enabled_for_domain(domain):
        return True

    def get_payload(self, repeat_record, payload_doc):
        raise NotImplementedError()

    def get_headers(self):
        return {}

    def get_test_payload(self):
        return (
            "<?xml version='1.0' ?>"
            "<data id='test'>"
            "<TestString>Test post from CommCareHQ on %s</TestString>"
            "</data>" % datetime.utcnow()
        )


@RegisterGenerator(FormRepeater, 'form_xml', 'XML', is_default=True)
class FormRepeaterXMLPayloadGenerator(BasePayloadGenerator):
    def get_payload(self, repeat_record, payload_doc):
        return payload_doc.get_xml()

    def get_test_payload(self):
        return self.get_payload(None, _get_test_form())


@RegisterGenerator(CaseRepeater, 'case_xml', 'XML', is_default=True)
class CaseRepeaterXMLPayloadGenerator(BasePayloadGenerator):
    def get_payload(self, repeat_record, payload_doc):
        return payload_doc.to_xml(self.repeater.version or V2, include_case_on_closed=True)

    def get_headers(self):
        return {'Content-type': 'application/json'}

    def get_test_payload(self):
        from casexml.apps.case.mock import CaseBlock
        return CaseBlock(
            case_id='test-case-%s' % uuid4().hex,
            create=True,
            case_type='test',
            case_name='test case',
        ).as_string()


@RegisterGenerator(CaseRepeater, 'case_json', 'JSON', is_default=False)
class CaseRepeaterJsonPayloadGenerator(BasePayloadGenerator):
    def get_payload(self, repeat_record, payload_doc):
        del payload_doc['actions']
        data = payload_doc.get_json(lite=True)
        return json.dumps(data, cls=DjangoJSONEncoder)

    def get_headers(self):
        return {'Content-type': 'application/json'}

    def get_test_payload(self):
        from casexml.apps.case.models import CommCareCase
        return self.get_payload(
            None,
            CommCareCase(
                domain='demo-domain', type='case_type', name='Demo',
                user_id='user1', prop_a=True, prop_b='value'
            )
        )


@RegisterGenerator(AppStructureRepeater, "app_structure_xml", "XML", is_default=True)
class AppStructureGenerator(BasePayloadGenerator):
    def get_payload(self, repeat_record, payload_doc):
        # This is the id of the application, currently all we forward
        return repeat_record.payload_id


@RegisterGenerator(ShortFormRepeater, "short_form_json", "Default JSON", is_default=True)
class ShortFormRepeaterJsonPayloadGenerator(BasePayloadGenerator):
    def get_payload(self, repeat_record, form):
        cases = cases_referenced_by_xform(form)
        return json.dumps({'form_id': form._id,
                           'received_on': json_format_datetime(form.received_on),
                           'case_ids': [case._id for case in cases]})

    def get_headers(self):
        return {'Content-type': 'application/json'}

    def get_test_payload(self):
        return json.dumps({
            'form_id': 'test-form-' + uuid4().hex,
            'received_on': json_format_datetime(datetime.utcnow()),
            'case_ids': ['test-case-' + uuid4().hex, 'test-case-' + uuid4().hex]
        })


@RegisterGenerator(FormRepeater, "form_json", "JSON", is_default=False)
class FormRepeaterJsonPayloadGenerator(BasePayloadGenerator):
    def get_payload(self, repeat_record, form):
        from corehq.apps.api.resources.v0_4 import XFormInstanceResource
        res = XFormInstanceResource()
        bundle = res.build_bundle(obj=form)
        return res.serialize(None, res.full_dehydrate(bundle), 'application/json')

    def get_headers(self):
        return {'Content-type': 'application/json'}

    def get_test_payload(self):
        return self.get_payload(None, _get_test_form())
