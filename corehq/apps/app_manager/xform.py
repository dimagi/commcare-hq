from collections import defaultdict, OrderedDict
from functools import wraps
import logging

import itertools
from django.utils.translation import ugettext_lazy as _

import formtranslate.api
from casexml.apps.case.xml import V2_NAMESPACE
from casexml.apps.stock.const import COMMTRACK_REPORT_XMLNS
from corehq.apps import nimbus_api
from corehq.apps.app_manager.const import (
    SCHEDULE_PHASE, SCHEDULE_LAST_VISIT, SCHEDULE_LAST_VISIT_DATE,
    CASE_ID, USERCASE_ID, SCHEDULE_UNSCHEDULED_VISIT, SCHEDULE_CURRENT_VISIT_NUMBER,
    SCHEDULE_GLOBAL_NEXT_VISIT_DATE, SCHEDULE_NEXT_DUE, APP_V2)
from lxml import etree as ET

from corehq.apps.nimbus_api.exceptions import NimbusAPIException
from corehq.toggles import NIMBUS_FORM_VALIDATION
from corehq.util.view_utils import get_request
from dimagi.utils.decorators.memoized import memoized
from .xpath import CaseIDXPath, session_var, CaseTypeXpath, QualifiedScheduleFormXPath
from .exceptions import XFormException, CaseError, XFormValidationError, BindNotFound, XFormValidationFailed
import collections
import re


VALID_VALUE_FORMS = ('image', 'audio', 'video', 'video-inline', 'markdown')


def parse_xml(string):
    # Work around: ValueError: Unicode strings with encoding
    # declaration are not supported.
    if isinstance(string, unicode):
        string = string.encode("utf-8")
    try:
        return ET.fromstring(string, parser=ET.XMLParser(encoding="utf-8", remove_comments=True))
    except ET.ParseError, e:
        raise XFormException(_(u"Error parsing XML: {}").format(e))


namespaces = dict(
    jr="{http://openrosa.org/javarosa}",
    xsd="{http://www.w3.org/2001/XMLSchema}",
    h='{http://www.w3.org/1999/xhtml}',
    f='{http://www.w3.org/2002/xforms}',
    ev="{http://www.w3.org/2001/xml-events}",
    orx="{http://openrosa.org/jr/xforms}",
    reg="{http://openrosa.org/user/registration}",
    cx2="{%s}" % V2_NAMESPACE,
    cc="{http://commcarehq.org/xforms}",
    v="{http://commcarehq.org/xforms/vellum}",
    odk="{http://opendatakit.org/xforms}",
)

HashtagReplacement = collections.namedtuple('HashtagReplacement', 'hashtag replaces')
hashtag_replacements = [
    HashtagReplacement(hashtag='#form/', replaces=r'^/data\/'),
]


def _make_elem(tag, attr=None):
    attr = attr or {}
    return ET.Element(
        tag.format(**namespaces),
        {key.format(**namespaces): val for key, val in attr.items()}
    )


def make_case_elem(tag, attr=None):
    return _make_elem(case_elem_tag(tag), attr)


def case_elem_tag(tag):
    return '{cx2}%s' % tag


def get_case_parent_id_xpath(parent_path, case_id_xpath=None):
    xpath = case_id_xpath or SESSION_CASE_ID
    if parent_path:
        for parent_name in parent_path.split('/'):
            xpath = xpath.case().index_id(parent_name)
    return xpath


def relative_path(from_path, to_path):
    from_nodes = from_path.split('/')
    to_nodes = to_path.split('/')
    while True:
        if to_nodes[0] == from_nodes[0]:
            from_nodes.pop(0)
            to_nodes.pop(0)
        else:
            break

    return '%s/%s' % ('/'.join(['..' for n in from_nodes]), '/'.join(to_nodes))


def requires_itext(on_fail_return=None):
    def _wrapper(func):
        @wraps(func)
        def _inner(self, *args, **kwargs):
            try:
                self.itext_node
            except XFormException:
                return on_fail_return() if on_fail_return else None
            return func(self, *args, **kwargs)
        return _inner
    return _wrapper


SESSION_CASE_ID = CaseIDXPath(session_var(CASE_ID))
SESSION_USERCASE_ID = CaseIDXPath(session_var(USERCASE_ID))


class WrappedAttribs(object):

    def __init__(self, attrib, namespaces=namespaces):
        self.attrib = attrib
        self.namespaces = namespaces

    def __getattr__(self, name):
        return getattr(self.attrib, name)

    def _get_item_name(self, item):
        return item if item.startswith('{http') else item.format(**self.namespaces)

    def __contains__(self, item):
        return self._get_item_name(item) in self.attrib

    def __iter__(self):
        raise NotImplementedError()

    def __setitem__(self, item, value):
        self.attrib[self._get_item_name(item)] = value

    def get(self, item, default=None):
        try:
            return self[item]
        except KeyError:
            return default

    def __getitem__(self, item):
        return self.attrib[self._get_item_name(item)]

    def __delitem__(self, item):
        del self.attrib[self._get_item_name(item)]


class WrappedNode(object):

    def __init__(self, xml, namespaces=namespaces):
        if isinstance(xml, basestring):
            self.xml = parse_xml(xml) if xml else None
        else:
            self.xml = xml
        self.namespaces = namespaces

    def xpath(self, xpath, *args, **kwargs):
        if self.xml is not None:
            return [WrappedNode(n) for n in self.xml.xpath(
                    xpath.format(**self.namespaces), *args, **kwargs)]
        else:
            return []

    def find(self, xpath, *args, **kwargs):
        if self.xml is not None:
            return WrappedNode(self.xml.find(
                xpath.format(**self.namespaces), *args, **kwargs))
        else:
            return WrappedNode(None)

    def findall(self, xpath, *args, **kwargs):
        if self.xml is not None:
            return [WrappedNode(n) for n in self.xml.findall(
                    xpath.format(**self.namespaces), *args, **kwargs)]
        else:
            return []

    def iterfind(self, xpath, *args, **kwargs):
        if self.xml is None:
            return
        formatted_xpath = xpath.format(**self.namespaces)
        for n in self.xml.iterfind(formatted_xpath, *args, **kwargs):
            yield WrappedNode(n)

    def findtext(self, xpath, *args, **kwargs):
        if self.xml is not None:
            return self.xml.findtext(
                xpath.format(**self.namespaces), *args, **kwargs)
        else:
            return None

    @property
    def attrib(self):
        return WrappedAttribs(self.xml.attrib, namespaces=self.namespaces)

    def __getattr__(self, attr):
        return getattr(self.xml, attr)

    def __nonzero__(self):
        return self.xml is not None

    def __len__(self):
        return len(self.xml) if self.exists() else 0

    @property
    def tag_xmlns(self):
        return self.tag.split('}')[0][1:]

    @property
    def tag_name(self):
        return self.tag.split('}')[1]

    def exists(self):
        return self.xml is not None

    def render(self):
        return ET.tostring(self.xml)


class ItextNodeGroup(object):

    def __init__(self, nodes):
        self.id = nodes[0].id
        assert all(node.id == self.id for node in nodes)
        self.nodes = dict((n.lang, n) for n in nodes)

    def add_node(self, node):
        if self.nodes.get(node.lang):
            raise XFormException(_(u"Group already has node for lang: {0}").format(node.lang))
        else:
            self.nodes[node.lang] = node

    def __eq__(self, other):
        for lang, node in self.nodes.items():
            other_node = other.nodes.get(lang)
            if node.rendered_values != other_node.rendered_values:
                return False

        return True

    def __hash__(self):
        return ''.join(["{0}{1}".format(n.lang, n.rendered_values) for n in self.nodes.values()]).__hash__()

    def __repr__(self):
        return "{0}, {1}".format(self.id, self.nodes)


class ItextNode(object):

    def __init__(self, lang, itext_node):
        self.lang = lang
        self.id = itext_node.attrib['id']
        values = itext_node.findall('{f}value')
        self.values_by_form = {value.attrib.get('form'): value for value in values}

    @property
    @memoized
    def rendered_values(self):
        return sorted([str.strip(ET.tostring(v.xml)) for v in self.values_by_form.values()])

    def __repr__(self):
        return self.id


class ItextOutput(object):

    def __init__(self, ref):
        self.ref = ref

    def render(self, context):
        return context.get(self.ref)


class ItextValue(unicode):

    def __new__(cls, parts):
        return super(ItextValue, cls).__new__(cls, cls._render(parts))

    def __init__(self, parts):
        super(ItextValue, self).__init__()
        self.parts = parts
        self.context = {}

    def with_refs(self, context, processor=None, escape=None):
        return self._render(self.parts, context, processor=processor,
                            escape=escape)

    @classmethod
    def from_node(cls, node):
        parts = [node.text or '']
        for sub in node.findall('*'):
            if sub.tag_name == 'output':
                ref = sub.attrib.get('ref') or sub.attrib.get('value')
                if ref:
                    parts.append(ItextOutput(ref=ref))
            parts.append(sub.tail or '')
        return cls(parts)

    @classmethod
    def _render(cls, parts, context=None, processor=None, escape=None):
        escape = escape or (lambda x: x)
        processor = processor or (lambda x: x if x is not None else '____')
        context = context or {}
        return ''.join(
            processor(part.render(context)) if hasattr(part, 'render')
            else escape(part)
            for part in parts
        )


def raise_if_none(message):
    """
    raise_if_none("message") is a decorator that turns a function that returns a WrappedNode
    whose xml can possibly be None to a function that always returns a valid WrappedNode or raises
    an XFormException with the message given

    """
    def decorator(fn):
        def _fn(*args, **kwargs):
            n = fn(*args, **kwargs)
            if not n.exists():
                raise XFormException(message)
            else:
                return n
        return _fn
    return decorator


class CaseBlock(object):

    @classmethod
    def make_parent_case_block(cls, xform, node_path, parent_path, case_id_xpath=None):
        case_block = CaseBlock(xform, node_path)
        id_xpath = get_case_parent_id_xpath(parent_path, case_id_xpath=case_id_xpath)
        xform.add_bind(
            nodeset='%scase/@case_id' % node_path,
            calculate=id_xpath,
        )
        return case_block

    def __init__(self, xform, path=''):
        self.xform = xform
        self.path = path

        self.elem = ET.Element('{cx2}case'.format(**namespaces), {
            'case_id': '',
            'date_modified': '',
            'user_id': '',
            }, nsmap={
            None: namespaces['cx2'][1:-1]
        })

        self.xform.add_bind(
            nodeset="%scase/@date_modified" % path,
            type="xsd:dateTime",
            calculate=self.xform.resolve_path("meta/timeEnd")
        )
        self.xform.add_bind(
            nodeset="%scase/@user_id" % path,
            calculate=self.xform.resolve_path("meta/userID"),
        )

    def add_create_block(self, relevance, case_name, case_type,
                         delay_case_id=False, autoset_owner_id=True,
                         has_case_sharing=False, case_id='uuid()',
                         make_relative=False):
        create_block = make_case_elem('create')
        self.elem.append(create_block)
        case_type_node = make_case_elem('case_type')
        owner_id_node = make_case_elem('owner_id')
        case_type_node.text = case_type

        create_block.append(make_case_elem('case_name'))
        create_block.append(owner_id_node)
        create_block.append(case_type_node)

        def add_setvalue_or_bind(ref, value):
            if not delay_case_id:
                self.xform.add_setvalue(ref=ref, value=value)
            else:
                self.xform.add_bind(nodeset=ref, calculate=value)

        self.xform.add_bind(
            nodeset='%scase' % self.path,
            relevant=relevance,
        )
        add_setvalue_or_bind(
            ref='%scase/@case_id' % self.path,
            value=case_id,
        )

        nodeset = self.xform.resolve_path("%scase/create/case_name" % self.path)
        name_path = self.xform.resolve_path(case_name)
        if make_relative:
            name_path = relative_path(nodeset, name_path)

        self.xform.add_bind(
            nodeset=nodeset,
            calculate=name_path,
        )

        if not autoset_owner_id:
            owner_id_node.text = '-'
        elif has_case_sharing:
            self.xform.add_instance('groups', src='jr://fixture/user-groups')
            add_setvalue_or_bind(
                ref="%scase/create/owner_id" % self.path,
                value="instance('groups')/groups/group/@id"
            )
        else:
            self.xform.add_bind(
                nodeset="%scase/create/owner_id" % self.path,
                calculate=self.xform.resolve_path("meta/userID"),
            )

        if not case_name:
            raise CaseError("Please set 'Name according to question'. "
                            "This will give each case a 'name' attribute")
        self.xform.add_bind(
            nodeset=case_name,
            required="true()",
        )

    @property
    @memoized
    def update_block(self):
        update_block = make_case_elem('update')
        self.elem.append(update_block)
        return update_block

    def add_update_block(self, updates, make_relative=False):
        update_block = self.update_block
        if not updates:
            return

        update_mapping = {}
        attachments = {}
        for key, value in updates.items():
            if key == 'name':
                key = 'case_name'
            if self.is_attachment(value):
                attachments[key] = value
            else:
                update_mapping[key] = value

        for key, q_path in sorted(update_mapping.items()):
            update_block.append(make_case_elem(key))
            nodeset = self.xform.resolve_path("%scase/update/%s" % (self.path, key))
            resolved_path = self.xform.resolve_path(q_path)
            if make_relative:
                resolved_path = relative_path(nodeset, resolved_path)

            self.xform.add_bind(
                nodeset=nodeset,
                calculate=resolved_path,
                relevant=("count(%s) > 0" % resolved_path)
            )

        if attachments:
            attachment_block = make_case_elem('attachment')
            self.elem.append(attachment_block)
            for key, q_path in sorted(attachments.items()):
                attach_elem = make_case_elem(key, {'src': '', 'from': 'local'})
                attachment_block.append(attach_elem)
                nodeset = self.xform.resolve_path(
                    "%scase/attachment/%s" % (self.path, key))
                resolved_path = self.xform.resolve_path(q_path)
                if make_relative:
                    resolved_path = relative_path(nodeset, resolved_path)
                self.xform.add_bind(nodeset=nodeset, relevant=("count(%s) = 1" % resolved_path))
                self.xform.add_bind(nodeset=nodeset + "/@src", calculate=resolved_path)

        return update_block

    def is_attachment(self, ref):
        """Return true if there is an upload node with the given ref """
        try:
            uploads = self.xform.__upload_refs
        except AttributeError:
            itr = self.xform.find('{h}body').iterfind(".//{f}upload[@ref]")
            uploads = self.xform.__upload_refs = set(node.attrib["ref"] for node in itr)
        return ref in uploads

    def add_close_block(self, relevance):
        self.elem.append(make_case_elem('close'))
        self.xform.add_bind(
            nodeset="%scase/close" % self.path,
            relevant=relevance,
        )

    def add_index_ref(self, reference_id, case_type, ref, relationship='child'):
        """
        When an index points to a parent case, its relationship attribute is
        set to "child". When it points to a host case, relationship is set to
        "extension".
        """
        index_node = self.elem.find('{cx2}index'.format(**namespaces))
        if index_node is None:
            index_node = make_case_elem('index')
            self.elem.append(index_node)
        if relationship not in ('child', 'extension'):
            raise CaseError('Valid values for an index relationship are "child" and "extension"')
        if relationship == 'child':
            case_index = make_case_elem(reference_id, {'case_type': case_type})
        else:
            case_index = make_case_elem(reference_id, {'case_type': case_type, 'relationship': relationship})
        index_node.append(case_index)

        self.xform.add_bind(
            nodeset='{path}case/index/{ref}'.format(path=self.path, ref=reference_id),
            calculate=ref,
        )


def autoset_owner_id_for_open_case(actions):
    return not ('update_case' in actions and
                'owner_id' in actions['update_case'].update)


def autoset_owner_id_for_subcase(subcase):
    return 'owner_id' not in subcase.case_properties


def autoset_owner_id_for_advanced_action(action):
    """
    The owner_id should be set if any indices are not 'extension'.
    If it was explicitly_set, never autoset it.
    """

    explicitly_set = ('owner_id' in action.case_properties)

    if explicitly_set:
        return False

    if not len(action.case_indices):
        return True

    for index in action.case_indices:
        if index.relationship == 'child':
            # if there is a child relationship, autoset
            return True
    # if there are only extension indices, don't autoset
    return False


def validate_xform(domain, source):
    if isinstance(source, unicode):
        source = source.encode("utf-8")
    # normalize and strip comments
    source = ET.tostring(parse_xml(source))
    if NIMBUS_FORM_VALIDATION.enabled(domain):
        try:
            validation_results = nimbus_api.validate_form(source)
        except NimbusAPIException:
            raise XFormValidationFailed("Unable to validate form")
    else:
        validation_results = formtranslate.api.validate(source)

    if not validation_results.success:
        raise XFormValidationError(
            fatal_error=validation_results.fatal_error,
            validation_problems=validation_results.problems,
        )


class XForm(WrappedNode):
    """
    A bunch of utility functions for doing certain specific
    tasks related to parsing and editing xforms.
    This is not a comprehensive API for xforms editing and parsing.

    """

    def __init__(self, *args, **kwargs):
        super(XForm, self).__init__(*args, **kwargs)
        if self.exists():
            xmlns = self.data_node.tag_xmlns
            self.namespaces.update(x="{%s}" % xmlns)
        self.has_casedb = False
        # A dictionary mapping case types to sets of scheduler case properties
        # updated by the form
        self._scheduler_case_updates = defaultdict(set)
        self._scheduler_case_updates_populated = False

    def __str__(self):
        return ET.tostring(self.xml) if self.xml is not None else ''

    @property
    @raise_if_none("Can't find <model>")
    def model_node(self):
        return self.find('{h}head/{f}model')

    @property
    @raise_if_none("Can't find <instance>")
    def instance_node(self):
        return self.model_node.find('{f}instance')

    @property
    @raise_if_none("Can't find data node")
    def data_node(self):
        return self.instance_node.find('*')

    @property
    @raise_if_none("Can't find <itext>")
    def itext_node(self):
        # awful, awful hack. It will be many weeks before I can look people in the eye again.
        return self.model_node.find('{f}itext') or self.model_node.find('itext')

    @property
    def case_node(self):
        v2_case_node = self.data_node.find('{cx2}case')
        if v2_case_node.exists():
            return v2_case_node
        else:
            return self.data_node.find('{x}case')

    @requires_itext(list)
    def media_references(self, form):
        nodes = self.itext_node.findall('{f}translation/{f}text/{f}value[@form="%s"]' % form)
        return list(set([n.text for n in nodes]))

    @requires_itext(list)
    def media_references_by_lang(self, lang, form):
        nodes = self.itext_node.findall('{f}translation[@lang="%s"]/{f}text/{f}value[@form="%s"]' % (lang, form))
        return list(set([n.text for n in nodes]))

    @property
    def odk_intents(self):
        nodes = self.findall('{h}head/{odk}intent')
        return list(set(n.attrib.get('class') for n in nodes))

    @property
    def text_references(self):
        nodes = self.findall('{h}head/{odk}intent[@class="org.commcare.dalvik.action.PRINT"]/{f}extra[@key="cc:print_template_reference"]')
        return list(set(n.attrib.get('ref').strip("'") for n in nodes))

    @property
    def image_references(self):
        return self.media_references(form="image")

    @property
    def audio_references(self):
        return self.media_references(form="audio")

    @property
    def video_references(self):
        return self.media_references(form="video") + self.media_references(form="video-inline")

    def all_media_references(self, lang):
        images = self.media_references_by_lang(lang=lang, form="image")
        video = self.media_references_by_lang(lang=lang, form="video")
        audio = self.media_references_by_lang(lang=lang, form="audio")
        inline_video = self.media_references_by_lang(lang=lang, form="video-inline")
        return images + video + audio + inline_video

    def get_instance_ids(self):
        def _get_instances():
            return itertools.chain(
                self.model_node.findall('{f}instance'),
                self.model_node.findall('instance')
            )

        return [
            instance.attrib['id']
            for instance in _get_instances()
            if 'id' in instance.attrib
        ]

    def set_name(self, new_name):
        title = self.find('{h}head/{h}title')
        if title.exists():
            title.xml.text = new_name
        try:
            self.data_node.set('name', "%s" % new_name)
        except XFormException:
            pass

    @memoized
    @requires_itext(dict)
    def translations(self):
        translations = OrderedDict()
        for translation in self.itext_node.findall('{f}translation'):
            lang = translation.attrib['lang']
            translations[lang] = translation

        return translations

    @memoized
    def itext_node_groups(self):
        """
        :return: dict mapping 'lang' to ItextNodeGroup objects.
        """
        node_groups = {}
        for lang, translation in self.translations().items():
            text_nodes = translation.findall('{f}text')
            for text in text_nodes:
                node = ItextNode(lang, text)
                group = node_groups.get(node.id)
                if not group:
                    group = ItextNodeGroup([node])
                else:
                    group.add_node(node)
                node_groups[node.id] = group

        return node_groups

    def _reset_translations_cache(self):
        self.translations.reset_cache(self)
        self.itext_node_groups.reset_cache(self)

    @requires_itext()
    def normalize_itext(self):
        """
        Convert this:
            id1: en => 'yes', sp => 'si'
            id2: en => 'yes', sp => 'si'
            id3: en => 'if', sp => 'si'

        to this:
            id1: en => 'yes', sp => 'si'
            id3: en => 'if', sp => 'si'

        and rename the appropriate label references.
        """
        translations = self.translations()
        node_groups = self.itext_node_groups()

        duplicate_dict = defaultdict(list)
        for g in node_groups.values():
            duplicate_dict[g].append(g)

        duplicates = [sorted(g, key=lambda ng: ng.id) for g in duplicate_dict.values() if len(g) > 1]

        for dup in duplicates:
            for group in dup[1:]:
                itext_ref = u'{{f}}text[@id="{0}"]'.format(group.id)
                for lang in group.nodes.keys():
                    translation = translations[lang]
                    node = translation.find(itext_ref)
                    translation.remove(node.xml)

        def replace_ref_s(xmlstring, find, replace):
            find = find.encode('ascii', 'xmlcharrefreplace')
            replace = replace.encode('ascii', 'xmlcharrefreplace')
            return xmlstring.replace(find, replace)

        xf_string = self.render()
        for dup in duplicates:
            reference = dup[0]
            new_ref = u"jr:itext('{0}')".format(reference.id)

            for group in dup[1:]:
                old_ref = u'jr:itext(\'{0}\')'.format(group.id)
                xf_string = replace_ref_s(xf_string, old_ref, new_ref)

        self.xml = parse_xml(xf_string)

        self._reset_translations_cache()

    def strip_vellum_ns_attributes(self):
        # vellum_ns is wrapped in braces i.e. '{http...}'
        vellum_ns = self.namespaces['v']
        xpath = ".//*[@*[namespace-uri()='{v}']]".format(v=vellum_ns[1:-1])
        for node in self.xpath(xpath):
            for key in node.xml.attrib:
                if key.startswith(vellum_ns):
                    del node.attrib[key]

    def add_missing_instances(self):
        from corehq.apps.app_manager.suite_xml.post_process.instances import get_all_instances_referenced_in_xpaths
        instance_declarations = self.get_instance_ids()
        missing_unknown_instances = set()
        instances, unknown_instance_ids = get_all_instances_referenced_in_xpaths('', [self.render()])
        for instance_id in unknown_instance_ids:
            if instance_id not in instance_declarations:
                missing_unknown_instances.add(instance_id)

        if missing_unknown_instances:
            instance_ids = "', '".join(missing_unknown_instances)
            raise XFormValidationError(_(
                "The form is missing some instance declarations "
                "that can't be automatically added: '%(instance_ids)s'"
            ) % {'instance_ids': instance_ids})

        for instance in instances:
            if instance.id not in instance_declarations:
                self.add_instance(instance.id, instance.src)

    @requires_itext()
    def rename_language(self, old_code, new_code):
        trans_node = self.translations().get(old_code)
        duplicate_node = self.translations().get(new_code)

        if not trans_node or not trans_node.exists():
            raise XFormException(_(u"There's no language called '{}'").format(old_code))
        if duplicate_node and duplicate_node.exists():
            raise XFormException(_(u"There's already a language called '{}'").format(new_code))
        trans_node.attrib['lang'] = new_code

        self._reset_translations_cache()

    def exclude_languages(self, whitelist):
        changes = False
        for lang, trans_node in self.translations().items():
            if lang not in whitelist:
                self.itext_node.remove(trans_node.xml)
                changes = True

        if changes and not len(self.itext_node):
            raise XFormException(_(u"Form does not contain any translations for any of the build languages"))

        if changes:
            self._reset_translations_cache()

    def _normalize_itext_id(self, id):
        pre = 'jr:itext('
        post = ')'

        if id.startswith(pre) and post[-len(post):] == post:
            id = id[len(pre):-len(post)]
        if id[0] == id[-1] and id[0] in ('"', "'"):
            id = id[1:-1]

        return id

    def localize(self, id, lang=None, form=None):
        # fail hard if no itext node present
        self.itext_node

        id = self._normalize_itext_id(id)
        node_group = self.itext_node_groups().get(id)
        if not node_group:
            return None

        lang = lang or self.translations().keys()[0]
        text_node = node_group.nodes.get(lang)
        if not text_node:
            return None

        value_node = text_node.values_by_form.get(form)

        if value_node:
            text = ItextValue.from_node(value_node)
        else:
            for f in text_node.values_by_form.keys():
                if f not in VALID_VALUE_FORMS + (None,):
                    raise XFormException(_(
                        u'Unrecognized value of "form" attribute in \'<value form="{}">\'. '
                        u'"form" attribute is optional. Valid values are: "{}".').format(
                            f, u'", "'.join(VALID_VALUE_FORMS)
                    ))
            raise XFormException(_(u'<translation lang="{lang}"><text id="{id}"> node has no <value>').format(
                lang=lang, id=id
            ))

        return text

    def get_label_translations(self, prompt, langs):
        if prompt.tag_name == 'repeat':
            return self.get_label_translations(prompt.find('..'), langs)
        label_node = prompt.find('{f}label')
        translations = {}
        if label_node.exists() and 'ref' in label_node.attrib:
            for lang in langs:
                label = self.localize(label_node.attrib['ref'], lang)
                if label:
                    translations[lang] = label

        return translations

    def get_label_text(self, prompt, langs):
        if prompt.tag_name == 'repeat':
            return self.get_label_text(prompt.find('..'), langs)
        label_node = prompt.find('{f}label')
        label = ""
        if label_node.exists():
            if 'ref' in label_node.attrib:
                for lang in langs + [None]:
                    label = self.localize(label_node.attrib['ref'], lang)
                    if label is not None:
                        break
            elif label_node.text:
                label = label_node.text.strip()
            else:
                label = ""

        return label

    def resolve_path(self, path, path_context=""):
        if path == "":
            return path_context
        elif path is None:
            raise CaseError("Every case must have a name")
        elif path[0] == "/":
            return path
        elif not path_context:
            return "/%s/%s" % (self.data_node.tag_name, path)
        else:
            return "%s/%s" % (path_context, path)

    def hashtag_path(self, path):
        for hashtag, replaces in hashtag_replacements:
            path = re.sub(replaces, hashtag, path)
        return path

    @requires_itext(list)
    def get_languages(self):
        if not self.exists():
            return []

        return self.translations().keys()

    def get_questions(self, langs, include_triggers=False,
                      include_groups=False, include_translations=False, form=None):
        """
        parses out the questions from the xform, into the format:
        [{"label": label, "tag": tag, "value": value}, ...]

        if the xform is bad, it will raise an XFormException

        :param include_triggers: When set to True will return label questions as well as regular questions
        :param include_groups: When set will return repeats and group questions
        :param include_translations: When set to True will return all the translations for the question
        """

        if not self.exists():
            return []

        questions = []
        repeat_contexts = set()
        excluded_paths = set()

        control_nodes = self.get_control_nodes()
        leaf_data_nodes = self.get_leaf_data_nodes()

        for node, path, repeat, group, items, is_leaf, data_type, relevant, required in control_nodes:
            excluded_paths.add(path)
            if not is_leaf and not include_groups:
                continue

            if node.tag_name == 'trigger' and not include_triggers:
                continue

            if repeat is not None:
                repeat_contexts.add(repeat)

            question = {
                "label": self.get_label_text(node, langs),
                "tag": node.tag_name,
                "value": path,
                "repeat": repeat,
                "group": group,
                "type": data_type,
                "relevant": relevant,
                "required": required == "true()",
                "comment": self._get_comment(leaf_data_nodes, path),
                "hashtagValue": self.hashtag_path(path),
            }
            if include_translations:
                question["translations"] = self.get_label_translations(node, langs)

            if items is not None:
                options = []
                for item in items:
                    translation = self.get_label_text(item, langs)
                    try:
                        value = item.findtext('{f}value').strip()
                    except AttributeError:
                        raise XFormException(_(u"<item> ({}) has no <value>").format(translation))
                    option = {
                        'label': translation,
                        'value': value
                    }
                    if include_translations:
                        option['translations'] = self.get_label_translations(item, langs)
                    options.append(option)
                question['options'] = options
            questions.append(question)

        repeat_contexts = sorted(repeat_contexts, reverse=True)

        for path, data_node in leaf_data_nodes.iteritems():
            if path not in excluded_paths:
                bind = self.get_bind(path)
                try:
                    matching_repeat_context = [
                        rc for rc in repeat_contexts if path.startswith(rc + '/')
                    ][0]
                except IndexError:
                    matching_repeat_context = None
                question = {
                    "tag": "hidden",
                    "value": path,
                    "repeat": matching_repeat_context,
                    "group": matching_repeat_context,
                    "type": "DataBindOnly",
                    "calculate": bind.attrib.get('calculate') if hasattr(bind, 'attrib') else None,
                }

                # Include meta information about the stock entry
                if data_node.tag_name == 'entry':
                    parent = next(data_node.xml.iterancestors())
                    if parent:
                        is_stock_element = any(map(
                            lambda namespace: namespace == COMMTRACK_REPORT_XMLNS,
                            parent.nsmap.values()
                        ))
                        if is_stock_element:
                            question.update({
                                "stock_entry_attributes": dict(data_node.xml.attrib),
                                "stock_type_attributes": dict(parent.attrib),
                            })

                hashtag_path = self.hashtag_path(path)
                question.update({
                    "label": hashtag_path,
                    "hashtagValue": hashtag_path,
                })

                if include_translations:
                    question["translations"] = {}

                questions.append(question)

        return questions

    def get_control_nodes(self):
        if not self.exists():
            return []

        control_nodes = []

        def for_each_control_node(group, path_context="", repeat_context=None,
                                  group_context=None):
            """
            repeat_context is the path to the last enclosing repeat
            group_context is the path to the last enclosing group,
            including repeat groups

            """
            for node in group.findall('*'):
                is_leaf = False
                items = None
                tag = node.tag_name
                if node.tag_xmlns == namespaces['f'][1:-1] and tag != 'label':
                    path = self.resolve_path(self.get_path(node), path_context)
                    bind = self.get_bind(path)
                    data_type = infer_vellum_type(node, bind)
                    relevant = bind.attrib.get('relevant') if bind else None
                    required = bind.attrib.get('required') if bind else None
                    skip = False

                    if tag == "group":
                        if node.find('{f}repeat').exists():
                            skip = True
                            recursive_kwargs = dict(
                                group=node,
                                path_context=path,
                                repeat_context=repeat_context,
                                group_context=group_context,
                            )
                        else:
                            recursive_kwargs = dict(
                                group=node,
                                path_context=path,
                                repeat_context=repeat_context,
                                group_context=path,
                            )
                    elif tag == "repeat":
                        recursive_kwargs = dict(
                            group=node,
                            path_context=path,
                            repeat_context=path,
                            group_context=path,
                        )
                    else:
                        recursive_kwargs = None
                        is_leaf = True
                        if tag in ("select1", "select"):
                            items = node.findall('{f}item')

                    if not skip:
                        control_nodes.append((node, path, repeat_context,
                                              group_context, items, is_leaf,
                                              data_type, relevant, required))
                    if recursive_kwargs:
                        for_each_control_node(**recursive_kwargs)

        for_each_control_node(self.find('{h}body'))
        return control_nodes

    def _get_comment(self, leaf_data_nodes, path):
        try:
            return leaf_data_nodes[path].attrib.get('{v}comment')
        except KeyError:
            return None

    def get_path(self, node):
        # TODO: add safety tests so that when something fails it fails with a good error
        path = None
        if 'nodeset' in node.attrib:
            path = node.attrib['nodeset']
        elif 'ref' in node.attrib:
            path = node.attrib['ref']
        elif 'bind' in node.attrib:
            bind_id = node.attrib['bind']
            bind = self.model_node.find('{f}bind[@id="%s"]' % bind_id)
            if not bind.exists():
                raise BindNotFound('No binding found for %s' % bind_id)
            path = bind.attrib['nodeset']
        elif node.tag_name == "group":
            path = ""
        elif node.tag_name == "repeat":
            path = node.attrib['nodeset']
        else:
            raise XFormException(_(u"Node <{}> has no 'ref' or 'bind'").format(node.tag_name))
        return path

    def get_leaf_data_nodes(self):
        if not self.exists():
            return []

        data_nodes = {}

        def for_each_data_node(parent, path_context=""):
            children = parent.findall('*')
            for child in children:
                path = self.resolve_path(child.tag_name, path_context)
                for_each_data_node(child, path_context=path)
            if not children and path_context:
                data_nodes[path_context] = parent

        for_each_data_node(self.data_node)
        return data_nodes

    def add_case_and_meta(self, form):
        form.get_app().assert_app_v2()
        self.create_casexml_2(form)
        self.add_usercase(form)
        self.add_meta_2(form)

    def add_case_and_meta_advanced(self, form):
        self.create_casexml_2_advanced(form)
        self.add_meta_2(form)

    def already_has_meta(self):
        meta_blocks = set()
        for meta_xpath in ('{orx}meta', '{x}meta', '{orx}Meta', '{x}Meta'):
            meta = self.data_node.find(meta_xpath)
            if meta.exists():
                meta_blocks.add(meta)

        return meta_blocks

    def add_usercase_bind(self, usercase_path):
        self.add_bind(
            nodeset=usercase_path + 'case/@case_id',
            calculate=SESSION_USERCASE_ID,
        )

    def add_case_preloads(self, preloads, case_id_xpath=None):
        from corehq.apps.app_manager.util import split_path

        self.add_casedb()
        for nodeset, property_ in preloads.items():
            parent_path, property_ = split_path(property_)
            property_xpath = {
                'name': 'case_name',
                'owner_id': '@owner_id'
            }.get(property_, property_)

            id_xpath = get_case_parent_id_xpath(parent_path, case_id_xpath=case_id_xpath)
            self.add_setvalue(
                ref=nodeset,
                value=id_xpath.case().property(property_xpath),
            )

    def add_usercase(self, form):
        usercase_path = 'commcare_usercase/'
        actions = form.active_actions()

        if 'usercase_update' in actions and actions['usercase_update'].update:
            self.add_usercase_bind(usercase_path)
            usercase_block = _make_elem('{x}commcare_usercase')
            case_block = CaseBlock(self, usercase_path)
            case_block.add_update_block(actions['usercase_update'].update)
            usercase_block.append(case_block.elem)
            self.data_node.append(usercase_block)

        if 'usercase_preload' in actions and actions['usercase_preload'].preload:
            self.add_case_preloads(
                actions['usercase_preload'].preload,
                case_id_xpath=SESSION_USERCASE_ID
            )

    def add_meta_2(self, form):
        case_parent = self.data_node

        # Test all of the possibilities so that we don't end up with two "meta" blocks
        for meta in self.already_has_meta():
            case_parent.remove(meta.xml)

        self.add_instance('commcaresession', src='jr://instance/session')

        orx = namespaces['orx'][1:-1]
        nsmap = {None: orx, 'cc': namespaces['cc'][1:-1]}

        meta = ET.Element("{orx}meta".format(**namespaces), nsmap=nsmap)
        tags = (
            '{orx}deviceID',
            '{orx}timeStart',
            '{orx}timeEnd',
            '{orx}username',
            '{orx}userID',
            '{orx}instanceID',
            '{cc}appVersion',
        )
        if form.get_auto_gps_capture():
            tags += ('{cc}location',)
        for tag in tags:
            meta.append(ET.Element(tag.format(**namespaces), nsmap=nsmap))

        case_parent.append(meta)

        self.add_setvalue(
            ref="meta/deviceID",
            value="instance('commcaresession')/session/context/deviceid",
        )
        self.add_setvalue(
            ref="meta/timeStart",
            type="xsd:dateTime",
            value="now()",
        )
        self.add_setvalue(
            ref="meta/timeEnd",
            type="xsd:dateTime",
            event="xforms-revalidate",
            value="now()",
        )
        self.add_setvalue(
            ref="meta/username",
            value="instance('commcaresession')/session/context/username",
        )
        self.add_setvalue(
            ref="meta/userID",
            value="instance('commcaresession')/session/context/userid",
        )
        self.add_setvalue(
            ref="meta/instanceID",
            value="uuid()"
        )
        self.add_setvalue(
            ref="meta/appVersion",
            value="instance('commcaresession')/session/context/appversion"
        )

        # never add pollsensor to a pre-2.14 app
        if form.get_app().enable_auto_gps:
            if form.get_auto_gps_capture():
                self.add_pollsensor(ref=self.resolve_path("meta/location"))
            elif self.model_node.findall("{f}bind[@type='geopoint']"):
                self.add_pollsensor()

    @requires_itext()
    def set_default_language(self, lang):
        for this_lang, translation in self.translations().items():
            if this_lang == lang:
                translation.attrib['default'] = ""
            else:
                translation.attrib.pop('default', None)

    def set_version(self, version):
        """set the form's version attribute"""
        self.data_node.set('version', "%s" % version)

    def get_bind(self, path):
        return self.model_node.find('{f}bind[@nodeset="%s"]' % path)

    def add_bind(self, **d):
        if d.get('relevant') == 'true()':
            del d['relevant']
        d['nodeset'] = self.resolve_path(d['nodeset'])
        if len(d) > 1:
            bind = _make_elem('bind', d)
            conflicting = self.get_bind(bind.attrib['nodeset'])
            if conflicting.exists():
                for a in bind.attrib:
                    conflicting.attrib[a] = bind.attrib[a]
            else:
                self.model_node.append(bind)

    def add_instance(self, id, src):
        """
        Add an instance with an id and src if it doesn't exist already
        If the id already exists, DOES NOT overwrite.

        """
        instance_xpath = 'instance[@id="%s"]' % id
        conflicting = (
            self.model_node.find('{f}%s' % instance_xpath).exists() or
            self.model_node.find(instance_xpath).exists()
        )
        if not conflicting:
            # insert right after the main <instance> block
            first_instance = self.model_node.find('{f}instance')
            first_instance.addnext(_make_elem('instance', {'id': id, 'src': src}))

    def add_setvalue(self, ref, value, event='xforms-ready', type=None):
        ref = self.resolve_path(ref)
        self.model_node.append(_make_elem('setvalue', {'ref': ref, 'value': value, 'event': event}))
        if type:
            self.add_bind(nodeset=ref, type=type)

    def add_pollsensor(self, event="xforms-ready", ref=None):
        """
        <orx:pollsensor event="xforms-ready" ref="/data/meta/location" />
        <bind nodeset="/data/meta/location" type="geopoint"/>
        """
        if ref:
            self.model_node.append(_make_elem('{orx}pollsensor',
                                              {'event': event, 'ref': ref}))
            self.add_bind(nodeset=ref, type="geopoint")
        else:
            self.model_node.append(_make_elem('{orx}pollsensor', {'event': event}))

    def action_relevance(self, condition):
        if condition.type == 'always':
            return 'true()'
        elif condition.type == 'if':
            if condition.operator == 'selected':
                template = u"selected({path}, '{answer}')"
            elif condition.operator == 'boolean_true':
                template = u"{path}"
            else:
                template = u"{path} = '{answer}'"
            return template.format(
                path=self.resolve_path(condition.question),
                answer=condition.answer
            )
        else:
            return 'false()'

    def create_casexml_2(self, form):
        actions = form.active_actions()

        if form.requires == 'none' and 'open_case' not in actions and 'update_case' in actions:
            raise CaseError("To update a case you must either open a case or require a case to begin with")

        delegation_case_block = None
        if not actions or (form.requires == 'none' and 'open_case' not in actions):
            case_block = None
        else:
            extra_updates = {}
            case_block = CaseBlock(self)
            module = form.get_module()
            if form.requires != 'none':
                def make_delegation_stub_case_block():
                    path = 'cc_delegation_stub/'
                    DELEGATION_ID = 'delegation_id'
                    outer_block = _make_elem('{x}cc_delegation_stub', {DELEGATION_ID: ''})
                    delegation_case_block = CaseBlock(self, path)
                    delegation_case_block.add_close_block('true()')
                    session_delegation_id = "instance('commcaresession')/session/data/%s" % DELEGATION_ID
                    path_to_delegation_id = self.resolve_path("%s@%s" % (path, DELEGATION_ID))
                    self.add_setvalue(
                        ref="%s@%s" % (path, DELEGATION_ID),
                        value="if(count({d}) = 1, {d}, '')".format(d=session_delegation_id),
                    )
                    self.add_bind(
                        nodeset="%scase" % path,
                        relevant="%s != ''" % path_to_delegation_id,
                    )
                    self.add_bind(
                        nodeset="%scase/@case_id" % path,
                        calculate=path_to_delegation_id
                    )
                    outer_block.append(delegation_case_block.elem)
                    return outer_block

                if module.task_list.show:
                    delegation_case_block = make_delegation_stub_case_block()

            if 'open_case' in actions:
                open_case_action = actions['open_case']
                case_id_xpath = CaseIDXPath(session_var(form.session_var_for_action('open_case')))
                case_block.add_create_block(
                    relevance=self.action_relevance(open_case_action.condition),
                    case_name=open_case_action.name_path,
                    case_type=form.get_case_type(),
                    autoset_owner_id=autoset_owner_id_for_open_case(actions),
                    has_case_sharing=form.get_app().case_sharing,
                    case_id=case_id_xpath
                )
                if 'external_id' in actions['open_case'] and actions['open_case'].external_id:
                    extra_updates['external_id'] = actions['open_case'].external_id
            elif module.root_module_id and module.parent_select.active:
                # This is a submodule. case_id will have changed to avoid a clash with the parent case.
                # Case type is enough to ensure uniqueness for normal forms. No need to worry about a suffix.
                case_id = '_'.join((CASE_ID, form.get_case_type()))
                case_id_xpath = CaseIDXPath(session_var(case_id))
                self.add_bind(
                    nodeset="case/@case_id",
                    calculate=case_id_xpath,
                )
            else:
                self.add_bind(
                    nodeset="case/@case_id",
                    calculate=SESSION_CASE_ID,
                )
                case_id_xpath = SESSION_CASE_ID

            if 'update_case' in actions or extra_updates:
                self.add_case_updates(
                    case_block,
                    getattr(actions.get('update_case'), 'update', {}),
                    extra_updates=extra_updates,
                    # case_id_xpath is set based on an assumption about the way suite_xml.py determines the
                    # case_id. If suite_xml changes the way it sets case_id for case updates, this will break.
                    case_id_xpath=case_id_xpath
                )

            if 'close_case' in actions:
                case_block.add_close_block(self.action_relevance(actions['close_case'].condition))

            if 'case_preload' in actions:
                self.add_case_preloads(
                    actions['case_preload'].preload,
                    # (As above) case_id_xpath is set based on an assumption about the way suite_xml.py determines
                    # the case_id. If suite_xml changes the way it sets case_id for case updates, this will break.
                    case_id_xpath=case_id_xpath
                )

        if 'subcases' in actions:
            subcases = actions['subcases']
            repeat_contexts = defaultdict(int)
            for subcase in subcases:
                if subcase.repeat_context:
                    repeat_contexts[subcase.repeat_context] += 1

            for i, subcase in enumerate(subcases):
                if not form.get_app().case_type_exists(subcase.case_type):
                    raise CaseError("Case type (%s) for form (%s) does not exist" % (subcase.case_type, form.default_name()))
                if subcase.repeat_context:
                    base_path = '%s/' % subcase.repeat_context
                    parent_node = self.instance_node.find(
                        '/{x}'.join(subcase.repeat_context.split('/'))[1:]
                    )
                    nest = repeat_contexts[subcase.repeat_context] > 1
                    case_id = 'uuid()'
                else:
                    base_path = ''
                    parent_node = self.data_node
                    nest = True
                    case_id = session_var(form.session_var_for_action(subcase))

                if nest:
                    name = 'subcase_%s' % i
                    subcase_node = _make_elem('{x}%s' % name)
                    parent_node.append(subcase_node)
                    path = '%s%s/' % (base_path, name)
                else:
                    subcase_node = parent_node
                    path = base_path

                subcase_block = CaseBlock(self, path)
                subcase_node.insert(0, subcase_block.elem)
                subcase_block.add_create_block(
                    relevance=self.action_relevance(subcase.condition),
                    case_name=subcase.case_name,
                    case_type=subcase.case_type,
                    delay_case_id=bool(subcase.repeat_context),
                    autoset_owner_id=autoset_owner_id_for_subcase(subcase),
                    has_case_sharing=form.get_app().case_sharing,
                    case_id=case_id
                )

                subcase_block.add_update_block(subcase.case_properties)

                if subcase.close_condition.is_active():
                    subcase_block.add_close_block(self.action_relevance(subcase.close_condition))

                if case_block is not None and subcase.case_type != form.get_case_type():
                    reference_id = subcase.reference_id or 'parent'

                    subcase_block.add_index_ref(
                        reference_id,
                        form.get_case_type(),
                        self.resolve_path("case/@case_id"),
                    )

        case = self.case_node
        case_parent = self.data_node

        if case_block is not None:
            if case.exists():
                raise XFormException(_("You cannot use the Case Management UI "
                                       "if you already have a case block in your form."))
            else:
                case_parent.append(case_block.elem)
                if delegation_case_block is not None:
                    case_parent.append(delegation_case_block.elem)

        if not case_parent.exists():
            raise XFormException(_("Couldn't get the case XML from one of your forms. "
                             "A common reason for this is if you don't have the "
                             "xforms namespace defined in your form. Please verify "
                             'that the xmlns="http://www.w3.org/2002/xforms" '
                             "attribute exists in your form."))

    def _schedule_global_next_visit_date(self, form, case):
        """
        Adds the necessary hidden properties, fixture references, and calculations to
        get the global next visit date for schedule modules
        """
        forms = [f for f in form.get_phase().get_forms()
                 if getattr(f, 'schedule') and f.schedule.enabled]
        forms_due = []
        for form in forms:
            form_xpath = QualifiedScheduleFormXPath(form, form.get_phase(), form.get_module(), case)
            name = u"next_{}".format(form.schedule_form_id)
            forms_due.append(u"/data/{}".format(name))

            self.add_instance(
                form_xpath.fixture_id,
                u'jr://fixture/{}'.format(form_xpath.fixture_id)
            )

            if form.get_phase().id == 1:
                self.add_bind(
                    nodeset=u'/data/{}'.format(name),
                    calculate=form_xpath.first_visit_phase_set
                )
            else:
                self.add_bind(
                    nodeset=u'/data/{}'.format(name),
                    calculate=form_xpath.xpath_phase_set
                )

            self.data_node.append(_make_elem(name))

        self.add_bind(
            nodeset=u'/data/{}'.format(SCHEDULE_GLOBAL_NEXT_VISIT_DATE),
            calculate=u'date(min({}))'.format(','.join(forms_due))
        )
        self.data_node.append(_make_elem(SCHEDULE_GLOBAL_NEXT_VISIT_DATE))

        self.add_bind(
            nodeset=u'/data/{}'.format(SCHEDULE_NEXT_DUE),
            calculate=QualifiedScheduleFormXPath.next_visit_date(forms, case)
        )
        self.data_node.append(_make_elem(SCHEDULE_NEXT_DUE))

    def create_casexml_2_advanced(self, form):
        self._scheduler_case_updates_populated = True
        from corehq.apps.app_manager.util import split_path

        if not form.actions.get_all_actions():
            return

        def configure_visit_schedule_updates(update_block, action, session_case_id):
            case = session_case_id.case()
            schedule_form_xpath = QualifiedScheduleFormXPath(form, form.get_phase(), form.get_module(), case)

            self.add_instance(
                schedule_form_xpath.fixture_id,
                u'jr://fixture/{}'.format(schedule_form_xpath.fixture_id)
            )

            self.add_bind(
                nodeset=u'{}/case/update/{}'.format(action.form_element_name, SCHEDULE_PHASE),
                type="xs:integer",
                calculate=schedule_form_xpath.current_schedule_phase_calculation(
                    self.action_relevance(form.schedule.termination_condition),
                    self.action_relevance(form.schedule.transition_condition),
                )
            )
            update_block.append(make_case_elem(SCHEDULE_PHASE))
            self._add_scheduler_case_update(action.case_type, SCHEDULE_PHASE)

            self.add_bind(
                nodeset=u'/data/{}'.format(SCHEDULE_CURRENT_VISIT_NUMBER),
                calculate=schedule_form_xpath.next_visit_due_num
            )
            self.data_node.append(_make_elem(SCHEDULE_CURRENT_VISIT_NUMBER))

            self.add_bind(
                nodeset=u'/data/{}'.format(SCHEDULE_UNSCHEDULED_VISIT),
                calculate=schedule_form_xpath.is_unscheduled_visit,
            )
            self.data_node.append(_make_elem(SCHEDULE_UNSCHEDULED_VISIT))

            last_visit_num = SCHEDULE_LAST_VISIT.format(form.schedule_form_id)
            self.add_bind(
                nodeset=u'{}/case/update/{}'.format(action.form_element_name, last_visit_num),
                relevant=u"not(/data/{})".format(SCHEDULE_UNSCHEDULED_VISIT),
                calculate=u"/data/{}".format(SCHEDULE_CURRENT_VISIT_NUMBER),
            )
            update_block.append(make_case_elem(last_visit_num))
            self._add_scheduler_case_update(action.case_type, last_visit_num)

            last_visit_date = SCHEDULE_LAST_VISIT_DATE.format(form.schedule_form_id)
            self.add_bind(
                nodeset=u'{}/case/update/{}'.format(action.form_element_name, last_visit_date),
                type="xsd:dateTime",
                calculate=self.resolve_path("meta/timeEnd"),
                relevant=u"not(/data/{})".format(SCHEDULE_UNSCHEDULED_VISIT),
            )
            update_block.append(make_case_elem(last_visit_date))
            self._add_scheduler_case_update(action.case_type, last_visit_date)

            self._schedule_global_next_visit_date(form, case)

        def create_case_block(action, bind_case_id_xpath=None):
            tag = action.form_element_name
            path = tag + '/'
            base_node = _make_elem("{{x}}{0}".format(tag))
            self.data_node.append(base_node)
            case_block = CaseBlock(self, path=path)

            if bind_case_id_xpath:
                self.add_bind(
                    nodeset="%scase/@case_id" % path,
                    calculate=bind_case_id_xpath,
                )

            base_node.append(case_block.elem)
            return case_block, path

        def check_case_type(action):
            if not form.get_app().case_type_exists(action.case_type):
                raise CaseError("Case type (%s) for form (%s) does not exist" % (
                    action.case_type,
                    form.default_name())
                )

        module = form.get_module()
        has_schedule = (module.has_schedule and getattr(form, 'schedule', False) and form.schedule.enabled and
                        getattr(form.get_phase(), 'anchor', False))
        last_real_action = next(
            (action for action in reversed(form.actions.load_update_cases)
             if not (action.auto_select) and action.case_type == module.case_type),
            None
        )
        adjusted_datums = {}
        if module.root_module:
            # for child modules the session variable for a case may have been
            # changed to match the parent module.
            from corehq.apps.app_manager.suite_xml.sections.entries import EntriesHelper
            gen = EntriesHelper(form.get_app())
            datums_meta, _ = gen.get_datum_meta_assertions_advanced(module, form)
            # TODO: this dict needs to be keyed by something unique to the action
            adjusted_datums = {
                getattr(meta.action, 'case_tag', None): meta.datum.id
                for meta in datums_meta
                if meta.action
            }

        for action in form.actions.get_load_update_actions():
            var_name = adjusted_datums.get(action.case_tag, action.case_session_var)
            session_case_id = CaseIDXPath(session_var(var_name))
            if action.preload:
                self.add_casedb()
                for nodeset, property in action.preload.items():
                    parent_path, property = split_path(property)
                    property_xpath = {
                        'name': 'case_name',
                        'owner_id': '@owner_id'
                    }.get(property, property)

                    id_xpath = get_case_parent_id_xpath(parent_path, case_id_xpath=session_case_id)
                    self.add_setvalue(
                        ref=nodeset,
                        value=id_xpath.case().property(property_xpath),
                    )

            if action.case_properties or action.close_condition.type != 'never' or \
                    (has_schedule and action == last_real_action):
                update_case_block, path = create_case_block(action, session_case_id)
                if action.case_properties:
                    self.add_case_updates(
                        update_case_block,
                        action.case_properties,
                        base_node_path=path,
                        case_id_xpath=session_case_id)

                if action.close_condition.type != 'never':
                    update_case_block.add_close_block(self.action_relevance(action.close_condition))

                if has_schedule and action == last_real_action:
                    self.add_casedb()
                    configure_visit_schedule_updates(update_case_block.update_block, action, session_case_id)

        repeat_contexts = defaultdict(int)
        for action in form.actions.open_cases:
            if action.repeat_context:
                repeat_contexts[action.repeat_context] += 1

        def get_action_path(action, create_subcase_node=True):
            if action.repeat_context:
                base_path = '%s/' % action.repeat_context
                parent_node = self.instance_node.find(
                    '/{x}'.join(action.repeat_context.split('/'))[1:]
                )
                nest = repeat_contexts[action.repeat_context] > 1
            else:
                base_path = ''
                parent_node = self.data_node
                nest = True

            if nest:
                name = action.form_element_name
                path = '%s%s/' % (base_path, name)
                if create_subcase_node:
                    subcase_node = _make_elem('{x}%s' % name)
                    parent_node.append(subcase_node)
                else:
                    subcase_node = None
            else:
                subcase_node = parent_node
                path = base_path

            return path, subcase_node

        for action in form.actions.get_open_actions():
            check_case_type(action)

            case_id = 'uuid()' if action.repeat_context else session_var(action.case_session_var)

            path, subcase_node = get_action_path(action)

            open_case_block = CaseBlock(self, path)
            subcase_node.insert(0, open_case_block.elem)
            open_case_block.add_create_block(
                relevance=self.action_relevance(action.open_condition),
                case_name=action.name_path,
                case_type=action.case_type,
                delay_case_id=bool(action.repeat_context),
                autoset_owner_id=autoset_owner_id_for_advanced_action(action),
                has_case_sharing=form.get_app().case_sharing,
                case_id=case_id
            )

            if action.case_properties:
                open_case_block.add_update_block(action.case_properties)

            for case_index in action.case_indices:
                parent_meta = form.actions.actions_meta_by_tag.get(case_index.tag)
                reference_id = case_index.reference_id or 'parent'
                if parent_meta['type'] == 'load':
                    ref = CaseIDXPath(session_var(parent_meta['action'].case_session_var))
                else:
                    path, _ = get_action_path(parent_meta['action'], create_subcase_node=False)
                    ref = self.resolve_path("%scase/@case_id" % path)

                open_case_block.add_index_ref(
                    reference_id,
                    parent_meta['action'].case_type,
                    ref,
                    case_index.relationship,
                )

            if action.close_condition.type != 'never':
                open_case_block.add_close_block(self.action_relevance(action.close_condition))

    def add_casedb(self):
        if not self.has_casedb:
            self.add_instance('casedb', src='jr://instance/casedb')
            self.has_casedb = True

    def add_case_updates(self, case_block, updates, extra_updates=None, base_node_path=None, case_id_xpath=None):
        from corehq.apps.app_manager.util import split_path

        def group_updates_by_case(updates):
            """
            updates grouped by case. Example:
            input: {'name': ..., 'parent/name'}
            output: {'': {'name': ...}, 'parent': {'name': ...}}
            """
            updates_by_case = defaultdict(dict)
            for key, value in updates.items():
                path, name = split_path(key)
                updates_by_case[path][name] = value
            return updates_by_case

        updates_by_case = group_updates_by_case(updates)
        if extra_updates:
            updates_by_case[''].update(extra_updates)
        if '' in updates_by_case:
            # 90% use-case
            basic_updates = updates_by_case.pop('')
            if basic_updates:
                case_block.add_update_block(basic_updates)
        if updates_by_case:
            self.add_casedb()

            def make_nested_subnode(base_node, path):
                """
                path='x/y/z' will append <x><y><z/></y></x> to base_node
                """
                prev_node = base_node
                node = None
                for node_name in path.split('/'):
                    node = _make_elem('{x}%s' % node_name)
                    prev_node.append(node)
                    prev_node = node
                return node

            if base_node_path:
                node_xpath = "{{x}}{0}".format(base_node_path[:-1])
                base_node = self.data_node.find(node_xpath)
            else:
                base_node = self.data_node
            parent_base = _make_elem('{x}parents')
            base_node.append(parent_base)
            for parent_path, updates in sorted(updates_by_case.items()):
                node = make_nested_subnode(parent_base, parent_path)
                node_path = '%sparents/%s/' % (base_node_path or '', parent_path)
                parent_case_block = CaseBlock.make_parent_case_block(
                    self,
                    node_path,
                    parent_path,
                    case_id_xpath=case_id_xpath)
                parent_case_block.add_update_block(updates)
                node.append(parent_case_block.elem)

    def add_care_plan(self, form):
        from const import CAREPLAN_GOAL, CAREPLAN_TASK
        from corehq.apps.app_manager.util import split_path
        self.add_meta_2(form)
        self.add_instance('casedb', src='jr://instance/casedb')

        for property, nodeset in form.case_preload.items():
            parent_path, property = split_path(property)
            property_xpath = {
                'name': 'case_name',
                'owner_id': '@owner_id'
            }.get(property, property)

            id_xpath = {
                'parent': CaseIDXPath(session_var('case_id')),
                'goal': CaseIDXPath(session_var('case_id_goal'))
            }.get(parent_path.split('/')[-1])

            if id_xpath:
                self.add_setvalue(
                    ref=nodeset,
                    value=id_xpath.case().property(property_xpath),
                )
            else:
                raise CaseError("Unknown parent reference '{ref}' for case type '{type}'".format(
                    ref=parent_path,
                    type=form.get_case_type())
                )

        def add_parent_case_id(case_block):
            parent_case_id = _make_elem('parent_case_id')
            self.data_node.append(parent_case_id)
            self.add_bind(
                nodeset=self.resolve_path('parent_case_id'),
                calculate=session_var('case_id')
            )
            case_block.add_index_ref(
                'parent',
                form.get_parent_case_type(),
                self.resolve_path('parent_case_id')
            )

        if form.case_type == CAREPLAN_GOAL:
            if form.mode == 'create':
                case_block = CaseBlock(self)
                case_block.add_create_block(
                    relevance='true()',
                    case_name=form.name_path,
                    case_type=form.case_type,
                    autoset_owner_id=False,
                    case_id=session_var('case_id_goal_new')
                )

                case_block.add_update_block(form.case_updates())

                add_parent_case_id(case_block)

                # set case owner to whatever parent case owner is
                self.add_setvalue(
                    ref="case/create/owner_id",
                    value=CaseIDXPath(self.resolve_path('parent_case_id')).case().property('@owner_id'),
                    event='xforms-revalidate'
                )

                self.data_node.append(case_block.elem)
            elif form.mode == 'update':
                case_parent = self.data_node
                case_block = CaseBlock(self)
                case_block.add_update_block(form.case_updates())

                idx_path = CaseIDXPath(session_var('case_id_goal'))
                self.add_setvalue(
                    ref='case/@case_id',
                    value=session_var('case_id_goal')
                )

                case_block.add_close_block("%s = '%s'" % (form.close_path, 'yes'))

                # preload values from case
                self.add_setvalue(
                    ref=form.description_path,
                    value=idx_path.case().property('description')
                )
                self.add_setvalue(
                    ref=form.date_followup_path,
                    value=idx_path.case().property('date_followup')
                )

                # load task case ID's into child_tasks node
                self.add_setvalue(
                    ref=self.resolve_path('child_tasks'),
                    value="join(' ', %s)" % CaseTypeXpath(CAREPLAN_TASK).case().select(
                        'index/goal', session_var('case_id_goal'), quote=False
                    ).select('@status', 'open').slash('@case_id')
                )

                case_parent.append(case_block.elem)

                task_case_block = CaseBlock(self, path='tasks_to_close/')
                task_case_block.elem.append(make_case_elem('close'))
                self.add_bind(
                    nodeset=self.resolve_path('tasks_to_close/case/@case_id'),
                    calculate='selected-at(%s, ../../@index)' % self.resolve_path('child_tasks')
                )

                self.data_node.find('{x}tasks_to_close').append(task_case_block.elem)
        elif form.case_type == CAREPLAN_TASK:
            if form.mode == 'create':
                path = 'task_repeat/'
                case_block = CaseBlock(self, path=self.resolve_path(path))
                case_block.add_create_block(
                    relevance='true()',
                    case_name=form.name_path,
                    case_type=CAREPLAN_TASK,
                    autoset_owner_id=False,
                    delay_case_id=True,
                    make_relative=True
                )

                # set case owner to whatever parent case owner is
                self.add_bind(
                    nodeset="%scase/create/owner_id" % path,
                    calculate=CaseIDXPath(self.resolve_path('parent_case_id')).case().property('@owner_id')
                )

                case_block.add_update_block(form.case_updates(), make_relative=True)

                add_parent_case_id(case_block)
                case_block.add_index_ref('goal', CAREPLAN_GOAL, session_var('case_id_goal'))

                self.data_node.find('{x}task_repeat').append(case_block.elem)
            elif form.mode == 'update':
                case_block = CaseBlock(self)
                case_block.add_update_block(form.case_updates())

                self.add_setvalue(
                    ref='case/@case_id',
                    value=CaseIDXPath(session_var('case_id_task'))
                )
                relevance = "%s = '%s'" % (self.resolve_path(form.close_path), 'yes')
                case_block.add_close_block(relevance)
                self.data_node.append(case_block.elem)

    def get_scheduler_case_updates(self):
        """
        Return a dictionary where each key is a case type and each value is a
        set of case properties that this form updates on account of the scheduler module.
        """
        if not self._scheduler_case_updates_populated:
            raise Exception('Scheduler case updates have not yet been populated')
        return self._scheduler_case_updates

    def _add_scheduler_case_update(self, case_type, case_property):
        self._scheduler_case_updates[case_type].add(case_property)

VELLUM_TYPES = {
    "AndroidIntent": {
        'tag': 'input',
        'type': 'intent',
        'icon': 'icon-vellum-android-intent',
        'icon_bs3': 'fcc fcc-fd-android-intent',
    },
    "Audio": {
        'tag': 'upload',
        'media': 'audio/*',
        'type': 'binary',
        'icon': 'icon-vellum-audio-capture',
        'icon_bs3': 'fcc fcc-fd-audio-capture',
    },
    "Barcode": {
        'tag': 'input',
        'type': 'barcode',
        'icon': 'icon-vellum-android-intent',
        'icon_bs3': 'fcc fcc-fd-android-intent',
    },
    "DataBindOnly": {
        'icon': 'icon-vellum-variable',
        'icon_bs3': 'fcc fcc-fd-variable',
    },
    "Date": {
        'tag': 'input',
        'type': 'xsd:date',
        'icon': 'icon-calendar',
        'icon_bs3': 'fa fa-calendar',
    },
    "DateTime": {
        'tag': 'input',
        'type': 'xsd:dateTime',
        'icon': 'icon-vellum-datetime',
        'icon_bs3': 'fcc fcc-fd-datetime',
    },
    "Double": {
        'tag': 'input',
        'type': 'xsd:double',
        'icon': 'icon-vellum-decimal',
        'icon_bs3': 'fcc fcc-fd-decimal',
    },
    "FieldList": {
        'tag': 'group',
        'appearance': 'field-list',
        'icon': 'icon-reorder',
        'icon_bs3': 'fa fa-bars',
    },
    "Geopoint": {
        'tag': 'input',
        'type': 'geopoint',
        'icon': 'icon-map-marker',
        'icon_bs3': 'fa fa-map-marker',
    },
    "Group": {
        'tag': 'group',
        'icon': 'icon-folder-open',
        'icon_bs3': 'fa fa-folder-open',
    },
    "Image": {
        'tag': 'upload',
        'media': 'image/*',
        'type': 'binary',
        'icon': 'icon-camera',
        'icon_bs3': 'fa fa-camera',
    },
    "Int": {
        'tag': 'input',
        'type': ('xsd:int', 'xsd:integer'),
        'icon': 'icon-vellum-numeric',
        'icon_bs3': 'fcc fcc-fd-numeric',
    },
    "Long": {
        'tag': 'input',
        'type': 'xsd:long',
        'icon': 'icon-vellum-long',
        'icon_bs3': 'fcc fcc-fd-long',
    },
    "MSelect": {
        'tag': 'select',
        'icon': 'icon-vellum-multi-select',
        'icon_bs3': 'fcc fcc-fd-multi-select',
    },
    "PhoneNumber": {
        'tag': 'input',
        'type': ('xsd:string', None),
        'appearance': 'numeric',
        'icon': 'icon-signal',
        'icon_bs3': 'fa fa-signal',
    },
    "Repeat": {
        'tag': 'repeat',
        'icon': 'icon-retweet',
        'icon_bs3': 'fa fa-retweet',
    },
    "Secret": {
        'tag': 'secret',
        'type': ('xsd:string', None),
        'icon': 'icon-key',
        'icon_bs3': 'fa fa-key',
    },
    "Select": {
        'tag': 'select1',
        'icon': 'icon-vellum-single-select',
        'icon_bs3': 'fcc fcc-fd-single-select',
    },
    "Text": {
        'tag': 'input',
        'type': ('xsd:string', None),
        'icon': "icon-vellum-text",
        'icon_bs3': 'fcc fcc-fd-text',
    },
    "Time": {
        'tag': 'input',
        'type': 'xsd:time',
        'icon': 'icon-time',
        'icon_bs3': 'a fa-clock-o',
    },
    "Trigger": {
        'tag': 'trigger',
        'icon': 'icon-tag',
        'icon_bs3': 'fa fa-tag',
    },
    "Video": {
        'tag': 'upload',
        'media': 'video/*',
        'type': 'binary',
        'icon': 'icon-facetime-video',
        'icon_bs3': 'fa fa-video-camera',
    },
}


def _index_on_fields(dicts, fields):
    try:
        field, other_fields = fields[0], fields[1:]
    except IndexError:
        return dicts
    partition = defaultdict(list)
    left_over = []
    for dct in dicts:
        values = dct.get(field)
        if not isinstance(values, (tuple, list)):
            values = [values]
        for value in values:
            if value is not None:
                partition[value].append(dct)
            else:
                left_over.append(dct)

    # the index should by default return an index on the rest of the fields
    # if it doesn't recognize the value accessed for the current field
    # This is actually important: if <group appearance="poodles"> is a Group;
    # but <group appearance="field-list"> is a FieldList. Here, "poodles" is
    # not recognized so it continues searching through dicts that don't care
    # about the "appearance" field
    default = _index_on_fields(left_over, other_fields)
    index = defaultdict(lambda: default)
    # This line makes the return value more printable for debugging
    index[None] = default
    for key in partition:
        index[key] = _index_on_fields(partition[key], other_fields)
    return index


VELLUM_TYPE_INDEX = _index_on_fields(
    [{field: value for field, value in (dct.items() + [('name', key)])}
     for key, dct in VELLUM_TYPES.items()],
    ('tag', 'type', 'media', 'appearance')
)


def infer_vellum_type(control, bind):
    tag = control.tag_name
    data_type = bind.attrib.get('type') if bind else None
    media_type = control.attrib.get('mediatype')
    appearance = control.attrib.get('appearance')

    results = VELLUM_TYPE_INDEX[tag][data_type][media_type][appearance]
    try:
        result, = results
    except ValueError:
        logging.error('No vellum type found matching', extra={
            'tag': tag,
            'data_type': data_type,
            'media_type': media_type,
            'appearance': appearance,
            'request': get_request()
        })
        return None
    return result['name']
