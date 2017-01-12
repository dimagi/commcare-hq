import json

from datetime import datetime
from uuid import uuid4

from django.core.serializers.json import DjangoJSONEncoder
from casexml.apps.case.xform import cases_referenced_by_xform

from corehq.apps.repeaters.models import FormRepeater, CaseRepeater, ShortFormRepeater, \
    AppStructureRepeater, GeneratorCollection

from casexml.apps.case.xml import V2

from dimagi.utils.parsing import json_format_datetime


def _get_test_form(domain):
    from corehq.form_processor.utils import TestFormMetadata
    from corehq.form_processor.utils import get_simple_wrapped_form
    metadata = TestFormMetadata(domain=domain, xmlns=uuid4().hex, form_name='Demo Form')
    return get_simple_wrapped_form('test-form-' + uuid4().hex, metadata=metadata, save=False)


class BasePayloadGenerator(object):

    def __init__(self, repeater):
        self.repeater = repeater

    @property
    def content_type(self):
        return 'text/xml'

    @staticmethod
    def enabled_for_domain(domain):
        return True

    def get_payload(self, repeat_record, payload_doc):
        raise NotImplementedError()

    def get_headers(self):
        return {'Content-Type': self.content_type}

    def get_test_payload(self, domain):
        return (
            "<?xml version='1.0' ?>"
            "<data id='test'>"
            "<TestString>Test post from CommCareHQ on %s</TestString>"
            "</data>" % datetime.utcnow()
        )

    def handle_success(self, response, payload_doc, repeat_record):
        """handle a successful post

        e.g. could be used to store something to the payload_doc once a
        response is recieved

        """
        return True

    def handle_failure(self, response, payload_doc, repeat_record):
        """handle a failed post
        """
        return True

    def handle_exception(self, exception, repeat_record):
        """handle an exception
        """
        return True


class RegisterGenerator(object):
    """Decorator to register new formats and Payload generators for Repeaters

    args:
        repeater_cls: A child class of Repeater for which the new format is being added
        format_name: unique identifier for the format
        format_label: description for the format

    kwargs:
        is_default: whether the format is default to the repeater_cls
    """

    generators = {}

    def __init__(self, repeater_cls, format_name, format_label, is_default=False):
        self.format_name = format_name
        self.format_label = format_label
        self.repeater_cls = repeater_cls
        self.label = format_label
        self.is_default = is_default

    def __call__(self, generator_class):
        if not self.repeater_cls in RegisterGenerator.generators:
            RegisterGenerator.generators[self.repeater_cls] = GeneratorCollection(self.repeater_cls)
        RegisterGenerator.generators[self.repeater_cls].add_new_format(
            self.format_name,
            self.format_label,
            generator_class,
            is_default=self.is_default
        )
        return generator_class

    @classmethod
    def generator_class_by_repeater_format(cls, repeater_class, format_name):
        """Return generator class given a Repeater class and format_name"""
        generator_collection = cls.generators[repeater_class]
        return generator_collection.get_generator_by_format(format_name)

    @classmethod
    def all_formats_by_repeater(cls, repeater_class, for_domain=None):
        """Return all formats for a given Repeater class"""
        generator_collection = cls.generators[repeater_class]
        return generator_collection.get_all_formats(for_domain=for_domain)

    @classmethod
    def default_format_by_repeater(cls, repeater_class):
        """Return default format_name for a Repeater class"""
        generator_collection = cls.generators[repeater_class]
        return generator_collection.get_default_format()


@RegisterGenerator(FormRepeater, 'form_xml', 'XML', is_default=True)
class FormRepeaterXMLPayloadGenerator(BasePayloadGenerator):

    def get_payload(self, repeat_record, payload_doc):
        return payload_doc.get_xml()

    def get_test_payload(self, domain):
        return self.get_payload(None, _get_test_form(domain))


@RegisterGenerator(CaseRepeater, 'case_xml', 'XML', is_default=True)
class CaseRepeaterXMLPayloadGenerator(BasePayloadGenerator):

    def get_payload(self, repeat_record, payload_doc):
        return payload_doc.to_xml(self.repeater.version or V2, include_case_on_closed=True)

    def get_test_payload(self, domain):
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
        data = payload_doc.to_api_json(lite=True)
        return json.dumps(data, cls=DjangoJSONEncoder)

    @property
    def content_type(self):
        return 'application/json'

    def get_test_payload(self, domain):
        from casexml.apps.case.models import CommCareCase
        return self.get_payload(
            None,
            CommCareCase(
                domain=domain, type='case_type', name='Demo',
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

    @property
    def content_type(self):
        return 'application/json'

    def get_test_payload(self, domain):
        return json.dumps({
            'form_id': 'test-form-' + uuid4().hex,
            'received_on': json_format_datetime(datetime.utcnow()),
            'case_ids': ['test-case-' + uuid4().hex, 'test-case-' + uuid4().hex]
        })


@RegisterGenerator(FormRepeater, "form_json", "JSON", is_default=False)
class FormRepeaterJsonPayloadGenerator(BasePayloadGenerator):

    def get_payload(self, repeat_record, form):
        from corehq.apps.api.resources.v0_4 import XFormInstanceResource
        from corehq.apps.api.util import form_to_es_form
        res = XFormInstanceResource()
        bundle = res.build_bundle(obj=form_to_es_form(form))
        return res.serialize(None, res.full_dehydrate(bundle), 'application/json')

    @property
    def content_type(self):
        return 'application/json'

    def get_test_payload(self, domain):
        return self.get_payload(None, _get_test_form(domain))
