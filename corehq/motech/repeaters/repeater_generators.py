import json
import warnings
from collections import namedtuple
from datetime import datetime
from uuid import uuid4

import attr

from django.core.serializers.json import DjangoJSONEncoder
from django.template.loader import render_to_string
from django.utils.translation import ugettext_lazy as _

from casexml.apps.case.xform import get_case_ids_from_form
from casexml.apps.case.xml import V2
from dimagi.utils.parsing import json_format_datetime

from corehq.apps.receiverwrapper.exceptions import DuplicateFormatException
from corehq.apps.users.models import CouchUser
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from corehq.motech.repeaters.exceptions import ReferralError


SYSTEM_FORM_XMLNS = 'http://commcarehq.org/case'


def _get_test_form(domain):
    from corehq.form_processor.utils import TestFormMetadata
    from corehq.form_processor.utils import get_simple_wrapped_form
    metadata = TestFormMetadata(domain=domain, xmlns=uuid4().hex, form_name='Demo Form')
    return get_simple_wrapped_form('test-form-' + uuid4().hex, metadata=metadata, save=False)


class BasePayloadGenerator(object):

    # you only have to override these
    # when there's more than one format option for a given repeater
    format_name = ''
    format_label = ""

    # if you ever change format_name, add the old format_name here for backwards compatability
    deprecated_format_names = ()

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


FormatInfo = namedtuple('FormatInfo', 'name label generator_class')


class GeneratorCollection(object):
    """Collection of format_name to Payload Generators for a Repeater class

    args:
        repeater_class: A valid child class of Repeater class
    """

    def __init__(self, repeater_class):
        self.repeater_class = repeater_class
        self.default_format = ''
        self.format_generator_map = {}

    def add_new_format(self, generator_class, is_default=False):
        """Adds a new format->generator mapping to the collection

        args:
            generator_class: child class of .repeater_generators.BasePayloadGenerator

        kwargs:
            is_default: True if the format_name should be default format

        exceptions:
            raises DuplicateFormatException if format is added with is_default while other
            default exists
            raises DuplicateFormatException if format_name alread exists in the collection
        """

        if is_default and self.default_format:
            raise DuplicateFormatException("A default format already exists for this repeater.")
        elif is_default:
            self.default_format = generator_class.format_name
        if generator_class.format_name in self.format_generator_map:
            raise DuplicateFormatException("There is already a Generator with this format name.")

        self.format_generator_map[generator_class.format_name] = FormatInfo(
            name=generator_class.format_name,
            label=generator_class.format_label,
            generator_class=generator_class
        )

    def get_default_format(self):
        """returns default format"""
        return self.default_format

    def get_default_generator(self):
        """returns generator class for the default format"""
        raise self.format_generator_map[self.default_format].generator_class

    def get_all_formats(self, for_domain=None):
        """returns all the formats added to this repeater collection"""
        return [(name, format.label) for name, format in self.format_generator_map.items()
                if not for_domain or format.generator_class.enabled_for_domain(for_domain)]

    def get_generator_by_format(self, format):
        """returns generator class given a format"""
        try:
            return self.format_generator_map[format].generator_class
        except KeyError:
            for info in self.format_generator_map.values():
                if format in info.generator_class.deprecated_format_names:
                    return info.generator_class
            raise


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
        warnings.warn(
            "Usage of @RegisterGenerator as a decorator is deprecated. "
            "Please put your payload generator classes in a tuple on your repeater class "
            "called payload_generator_classes instead.",
            DeprecationWarning)
        generator_class.format_label = self.format_label
        generator_class.format_name = self.format_name
        self.register_generator(generator_class, self.repeater_cls, is_default=self.is_default)
        return generator_class

    @classmethod
    def register_generator(cls, generator_class, repeater_class, is_default):
        cls.get_collection(repeater_class).add_new_format(generator_class, is_default)

    @classmethod
    def get_collection(cls, repeater_class):
        if repeater_class not in cls.generators:
            cls.generators[repeater_class] = GeneratorCollection(repeater_class)
            generator_classes = repeater_class.payload_generator_classes
            default_generator_class = generator_classes[0]
            for generator_class in generator_classes:
                cls.register_generator(
                    generator_class=generator_class,
                    repeater_class=repeater_class,
                    is_default=(generator_class is default_generator_class),
                )

        return cls.generators[repeater_class]

    @classmethod
    def generator_class_by_repeater_format(cls, repeater_class, format_name):
        """Return generator class given a Repeater class and format_name"""
        return cls.get_collection(repeater_class).get_generator_by_format(format_name)

    @classmethod
    def all_formats_by_repeater(cls, repeater_class, for_domain=None):
        """Return all formats for a given Repeater class"""
        return cls.get_collection(repeater_class).get_all_formats(for_domain=for_domain)

    @classmethod
    def default_format_by_repeater(cls, repeater_class):
        """Return default format_name for a Repeater class"""
        return cls.get_collection(repeater_class).get_default_format()


class FormRepeaterXMLPayloadGenerator(BasePayloadGenerator):
    format_name = 'form_xml'
    format_label = _("XML")

    def get_payload(self, repeat_record, payload_doc):
        return payload_doc.get_xml()

    def get_test_payload(self, domain):
        return self.get_payload(None, _get_test_form(domain))


class CaseRepeaterXMLPayloadGenerator(BasePayloadGenerator):
    format_name = 'case_xml'
    format_label = _("XML")

    def get_payload(self, repeat_record, payload_doc):
        return payload_doc.to_xml(self.repeater.version or V2, include_case_on_closed=True)

    def get_test_payload(self, domain):
        from casexml.apps.case.mock import CaseBlock
        return CaseBlock.deprecated_init(
            case_id='test-case-%s' % uuid4().hex,
            create=True,
            case_type='test',
            case_name='test case',
        ).as_text()


class CaseRepeaterJsonPayloadGenerator(BasePayloadGenerator):
    format_name = 'case_json'
    format_label = _('JSON')

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


@attr.s
class CaseTypeReferralConfig(object):
    #if false, listed_properties is a whitelist
    use_blacklist = attr.ib()
    listed_properties = attr.ib()
    constant_properties = attr.ib()


class ReferCasePayloadGenerator(BasePayloadGenerator):

    def get_payload(self, repeat_record, payload_doc):

        case_ids_to_forward = payload_doc.get_case_property('cases_to_forward')
        if not case_ids_to_forward:
            raise ReferralError(f'No cases included in transfer. Please add case ids to "cases_to_forward" property')
        else:
            case_ids_to_forward = case_ids_to_forward.split(' ')
        new_owner = payload_doc.get_case_property('new_owner')
        cases_to_forward = CaseAccessors(payload_doc.domain).get_cases(case_ids_to_forward)
        case_ids_to_forward = set(case_ids_to_forward)
        included_case_types = payload_doc.get_case_property('case_types').split(' ')
        case_type_configs = {}
        for case_type in included_case_types:
            constant_properties = []
            for key, value in payload_doc.case_json.items():
                constant_prefix = f'{case_type}_setter_'
                if key.startswith(constant_prefix):
                    property_name = key[len(constant_prefix):]
                    constant_properties.append((property_name, value))
            whitelist = payload_doc.case_json.get(f'{case_type}_whitelist')
            blacklist = payload_doc.case_json.get(f'{case_type}_blacklist')
            if blacklist and whitelist:
                raise ReferralError(f'both blacklist and whitelist included for {case_type}')
            if not blacklist and not whitelist:
                raise ReferralError(f'blacklist or whitelist not included for {case_type}')
            if blacklist:
                listed_properties = blacklist.split(' ')
                use_blacklist = True
            else:
                listed_properties = whitelist.split(' ')
                use_blacklist = False
            case_type_configs[case_type] = CaseTypeReferralConfig(
                use_blacklist,
                listed_properties,
                constant_properties
            )

        case_blocks = self._get_case_blocks(cases_to_forward, case_ids_to_forward, case_type_configs, new_owner)
        return render_to_string('hqcase/xml/case_block.xml', {
            'xmlns': SYSTEM_FORM_XMLNS,
            'case_block': case_blocks,
            'time': datetime.utcnow(),
            'uid': uuid4().hex,
            'username': self.repeater.username,
            'user_id': CouchUser.get_by_username(self.repeater.username).user_id,
            'device_id': "ReferCaseRepeater",
        })

    def _get_case_blocks(self, cases_to_forward, case_ids_to_forward, case_type_configs, new_owner):
        case_blocks = []
        case_id_map = {}
        for case in cases_to_forward:
            original_id = case.case_id
            indices = case.indices
            case.case_id = self._get_updated_case_id(original_id, case_id_map)
            case.owner_id = new_owner
            for index in indices:
                if index.referenced_id in case_ids_to_forward:
                    index.referenced_id = self._get_updated_case_id(index.referenced_id, case_id_map)
                else:
                    raise ReferralError(f'case {original_id} included without referenced case {index.referenced_id}')
            config = case_type_configs[case.type]
            if config.use_blacklist:
                self._update_case_properties_with_blacklist(case, config)
            else:
                self._update_case_properties_with_whitelist(case, config)
            self._set_constant_properties(case, config)
            self._set_referral_properties(case, original_id)
            case_blocks.append(case.to_xml(V2).decode('utf-8'))
        case_blocks = ''.join(case_blocks)
        return case_blocks

    def _get_updated_case_id(self, original_case_id, case_id_map):
        if original_case_id in case_id_map:
            new_case_id = case_id_map[original_case_id]
        else:
            new_case_id = uuid4().hex
            case_id_map[original_case_id] = new_case_id
        return new_case_id

    def _update_case_properties_with_blacklist(self, case, config):
        for name in config.listed_properties:
            if name in case.case_json:
                del case.case_json[name]

    def _update_case_properties_with_whitelist(self, case, config):
        new_json = {}
        for name in config.listed_properties:
            if name in case.case_json:
                new_json[name] = case.case_json[name]
        case.case_json = new_json

    def _set_constant_properties(self, case, config):
        for name, value in config.constant_properties:
            case.case_json[name] = value

    def _set_referral_properties(self, case, original_case_id):
        # make sure new case is open
        case.closed = False
        case.case_json['cchq_referral_source_domain'] = self.repeater.domain
        case.case_json['cchq_referral_source_case_id'] = original_case_id


class AppStructureGenerator(BasePayloadGenerator):

    deprecated_format_names = ('app_structure_xml',)

    def get_payload(self, repeat_record, payload_doc):
        # This is the id of the application, currently all we forward
        return repeat_record.payload_id


class ShortFormRepeaterJsonPayloadGenerator(BasePayloadGenerator):

    deprecated_format_names = ('short_form_json',)

    def get_payload(self, repeat_record, form):
        case_ids = list(get_case_ids_from_form(form))
        return json.dumps({'form_id': form.form_id,
                           'received_on': json_format_datetime(form.received_on),
                           'case_ids': case_ids})

    @property
    def content_type(self):
        return 'application/json'

    def get_test_payload(self, domain):
        return json.dumps({
            'form_id': 'test-form-' + uuid4().hex,
            'received_on': json_format_datetime(datetime.utcnow()),
            'case_ids': ['test-case-' + uuid4().hex, 'test-case-' + uuid4().hex]
        })


class FormRepeaterJsonPayloadGenerator(BasePayloadGenerator):

    format_name = 'form_json'
    format_label = _('JSON')

    def get_payload(self, repeat_record, form):
        from corehq.apps.api.resources.v0_4 import XFormInstanceResource
        from corehq.apps.api.util import form_to_es_form
        res = XFormInstanceResource()
        bundle = res.build_bundle(obj=form_to_es_form(form, include_attachments=True))
        return res.serialize(None, res.full_dehydrate(bundle), 'application/json')

    @property
    def content_type(self):
        return 'application/json'

    def get_test_payload(self, domain):
        return self.get_payload(None, _get_test_form(domain))


class UserPayloadGenerator(BasePayloadGenerator):

    @property
    def content_type(self):
        return 'application/json'

    def get_payload(self, repeat_record, user):
        from corehq.apps.api.resources.v0_5 import CommCareUserResource
        resource = CommCareUserResource(api_name='v0.5')
        bundle = resource.build_bundle(obj=user)
        return json.dumps(resource.full_dehydrate(bundle).data, cls=DjangoJSONEncoder)


class LocationPayloadGenerator(BasePayloadGenerator):

    @property
    def content_type(self):
        return 'application/json'

    def get_payload(self, repeat_record, location):
        return json.dumps(location.to_json())
