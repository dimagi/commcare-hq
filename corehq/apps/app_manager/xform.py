import collections
import itertools
import logging
import re
from collections import OrderedDict, defaultdict
from functools import wraps

from django.utils.translation import gettext_lazy as _

from lxml import etree as ET
from memoized import memoized
from requests import RequestException

from casexml.apps.case.const import UNOWNED_EXTENSION_OWNER_ID
from casexml.apps.case.xml import V2_NAMESPACE
from casexml.apps.stock.const import COMMTRACK_REPORT_XMLNS

from corehq.apps import formplayer_api
from corehq.apps.app_manager.const import (
    CASE_ID,
    UPDATE_MODE_EDIT,
    SCHEDULE_CURRENT_VISIT_NUMBER,
    SCHEDULE_GLOBAL_NEXT_VISIT_DATE,
    SCHEDULE_LAST_VISIT,
    SCHEDULE_LAST_VISIT_DATE,
    SCHEDULE_NEXT_DUE,
    SCHEDULE_PHASE,
    SCHEDULE_UNSCHEDULED_VISIT,
    USERCASE_ID,
)
from corehq.apps.app_manager.xpath import XPath, UsercaseXPath
from corehq.apps.formplayer_api.exceptions import FormplayerAPIException
from corehq.toggles import DONT_INDEX_SAME_CASETYPE, NAMESPACE_DOMAIN, SAVE_ONLY_EDITED_FORM_FIELDS
from corehq.util.view_utils import get_request

from .exceptions import (
    BindNotFound,
    CaseError,
    XFormException,
    XFormValidationError,
    XFormValidationFailed,
    DangerousXmlException,
)
from .suite_xml.xml_models import Instance
from .xpath import CaseIDXPath, QualifiedScheduleFormXPath, session_var

VALID_VALUE_FORMS = ('image', 'audio', 'video', 'video-inline', 'markdown')


def parse_xml(string):
    # Work around: ValueError: Unicode strings with encoding
    # declaration are not supported.
    if isinstance(string, str):
        string = string.encode("utf-8")

    parser = ET.XMLParser(encoding="utf-8", remove_comments=True, resolve_entities=False)
    try:
        parsed = ET.fromstring(string, parser=parser)
    except ET.ParseError as e:
        raise XFormException(_("Error parsing XML: {}").format(e))

    if _contains_entities(parsed):
        raise DangerousXmlException(_("Error parsing XML: Entities are not allowed"))

    return parsed


def _contains_entities(xml_element):
    tree = xml_element.getroottree()
    entities = tree.iter(ET.Entity)
    has_entities = any(True for _ in entities)  # Some entities evaluate to false, so changing them to True here
    return has_entities


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


def get_add_case_preloads_case_id_xpath(module, form):
    from corehq.apps.app_manager.suite_xml.sections.entries import EntriesHelper
    if 'open_case' in form.active_actions():
        return CaseIDXPath(session_var(form.session_var_for_action('open_case')))
    elif module.root_module_id or module.parent_select.active:
        # We could always get the var name from the datums but there's a performance cost
        # If the above conditions don't apply then it should always be 'case_id'
        var_name = EntriesHelper(module.get_app()).get_case_session_var_for_form(form)
        if var_name:
            return CaseIDXPath(session_var(var_name))
        raise CaseError("Unable to determine correct session variable for case management")
    return SESSION_CASE_ID


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
        if isinstance(xml, bytes):
            xml = xml.decode('utf-8')
        if isinstance(xml, str):
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
            return WrappedNode(self.xml.find(xpath.format(**self.namespaces), *args, **kwargs))
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

    def iterancestors(self, tag=None, *tags):
        if self.xml is not None:
            tags = [t.format(self.namespaces) for t in tags]
            for n in self.xml.iterancestors(tag.format(**self.namespaces), *tags):
                yield WrappedNode(n)

    @property
    def attrib(self):
        return WrappedAttribs(self.xml.attrib, namespaces=self.namespaces)

    def __getattr__(self, attr):
        return getattr(self.xml, attr)

    def __bool__(self):
        return self.xml is not None

    __nonzero__ = __bool__

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
        ET.indent(self.xml, level=0)
        return ET.tostring(self.xml, encoding='utf-8')


class ItextNodeGroup(object):

    def __init__(self, nodes):
        self.id = nodes[0].id
        assert all(node.id == self.id for node in nodes)
        self.nodes = dict((n.lang, n) for n in nodes)

    def add_node(self, node):
        if self.nodes.get(node.lang):
            raise XFormException(_("Group already has node for lang: {0}").format(node.lang))
        else:
            self.nodes[node.lang] = node

    def __eq__(self, other):
        for lang, node in self.nodes.items():
            other_node = other.nodes.get(lang)
            if node.rendered_values != other_node.rendered_values:
                return False

        return True

    def __hash__(self):
        return hash(''.join(["{0}{1}".format(n.lang, n.rendered_values) for n in self.nodes.values()]))

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
        return sorted([bytes.strip(ET.tostring(v.xml, encoding='utf-8')) for v in self.values_by_form.values()])

    def __repr__(self):
        return self.id


class ItextOutput(object):

    def __init__(self, ref):
        self.ref = ref

    def render(self, context):
        return context.get(self.ref)


class ItextValue(str):

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


class XFormCaseBlock(object):

    @classmethod
    def make_parent_case_block(cls, xform, node_path, parent_path, case_id_xpath=None):
        case_block = XFormCaseBlock(xform, node_path)
        id_xpath = get_case_parent_id_xpath(parent_path, case_id_xpath=case_id_xpath)
        case_block.bind_case_id(id_xpath, node_path)
        return case_block

    def __init__(self, xform, path=''):
        self.xform = xform
        self.path = path
        self.is_empty = True

    @property
    @memoized
    def elem(self):
        self.is_empty = False
        elem = ET.Element('{cx2}case'.format(**namespaces), {
            'case_id': '',
            'date_modified': '',
            'user_id': '',
            }, nsmap={
            None: namespaces['cx2'][1:-1]
        })

        self.xform.add_bind(
            nodeset="%scase/@date_modified" % self.path,
            type="xsd:dateTime",
            calculate=self.xform.resolve_path("meta/timeEnd")
        )
        self.xform.add_bind(
            nodeset="%scase/@user_id" % self.path,
            calculate=self.xform.resolve_path("meta/userID"),
        )
        return elem

    def bind_case_id(self, xpath, nodset_path=""):
        self.elem  # create case block
        self.xform.add_bind(
            nodeset=f"{nodset_path}case/@case_id",
            calculate=xpath,
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
            owner_id_node.text = UNOWNED_EXTENSION_OWNER_ID
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

    def add_case_updates(self, updates, make_relative=False, save_only_if_edited=False):
        from corehq.apps.app_manager.models import ConditionalCaseUpdate
        update_block = self.update_block
        if not updates:
            return

        update_mapping = {}
        attachments = {}
        for key, value in updates.items():
            value_str = getattr(value, "question_path", value)
            if key == 'name':
                key = 'case_name'
            if self.is_attachment(value_str):
                attachments[key] = value_str
            else:
                update_mapping[key] = value

        for key, q_path in sorted(update_mapping.items()):
            resolved_path = self.xform.resolve_path(q_path)
            edit_mode_expression = ''
            if (save_only_if_edited and isinstance(q_path, ConditionalCaseUpdate)
            and q_path.update_mode == UPDATE_MODE_EDIT):
                case_id_xpath = self.xform.resolve_path(f"{self.path}case/@case_id")
                case_value = CaseIDXPath(case_id_xpath).case().slash(key)
                self.xform.add_casedb()
                edit_mode_expression = f' and {case_value} != {resolved_path}'
            update_block.append(make_case_elem(key))
            nodeset = self.xform.resolve_path("%scase/update/%s" % (self.path, key))
            if make_relative:
                resolved_path = relative_path(nodeset, resolved_path)

            self.xform.add_bind(
                nodeset=nodeset,
                calculate=resolved_path,
                relevant=(f"count({resolved_path}) > 0" + edit_mode_expression)
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

        valid_relationships = ['child', 'extension', 'question']
        if relationship not in valid_relationships:
            raise CaseError('Valid values for an index relationship are: {}'.format(
                ', '.join(['"{}"'.format(r) for r in valid_relationships])))
        if relationship == 'child':
            case_index = make_case_elem(reference_id, {'case_type': case_type})
        elif relationship == 'extension':
            case_index = make_case_elem(reference_id, {'case_type': case_type, 'relationship': relationship})
        elif relationship == 'question':
            case_index = make_case_elem(reference_id, {'case_type': case_type, 'relationship': '@relationship'})

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

    relationships = [i.relationship for i in action.case_indices]
    if 'question' in relationships:
        # if there is a dynamically-determined relationship, don't autoset, the owner_id
        # bind will be added when the index is created rather than in add_create_block
        return False
    if 'child' in relationships:
        # if there is a child relationship, autoset
        return True
    # if there are only extension indices, don't autoset
    return False


def validate_xform(source):
    if isinstance(source, str):
        source = source.encode("utf-8")
    # normalize and strip comments
    source = ET.tostring(parse_xml(source), encoding='utf-8')
    try:
        validation_results = formplayer_api.validate_form(source)
    except FormplayerAPIException as err:
        if isinstance(err.__cause__, RequestException):
            raise XFormValidationFailed("Unable to connect to Formplayer")
        else:
            raise XFormValidationFailed("Unable to validate form")

    if not validation_results.success:
        raise XFormValidationError(
            fatal_error=validation_results.fatal_error,
            validation_problems=validation_results.problems,
        )


ControlNode = collections.namedtuple('ControlNode', ['node', 'bind_node', 'path', 'repeat', 'group', 'items',
                                     'is_leaf', 'data_type', 'relevant', 'required', 'constraint'])


class XForm(WrappedNode):
    """
    A bunch of utility functions for doing certain specific
    tasks related to parsing and editing xforms.
    This is not a comprehensive API for xforms editing and parsing.

    """

    def __init__(self, *args, domain=None, **kwargs):
        super(XForm, self).__init__(*args, **kwargs)
        if self.exists():
            xmlns = self.data_node.tag_xmlns
            self.namespaces.update(x="{%s}" % xmlns)
        self.has_casedb = False
        # A dictionary mapping case types to sets of scheduler case properties
        # updated by the form
        self._scheduler_case_updates = defaultdict(set)
        self._scheduler_case_updates_populated = False
        self.domain = domain
        if domain:
            self.save_only_if_edited = SAVE_ONLY_EDITED_FORM_FIELDS.enabled(domain, NAMESPACE_DOMAIN)
        else:
            self.save_only_if_edited = False

    def __str__(self):
        return ET.tostring(self.xml, encoding='utf-8').decode('utf-8') if self.xml is not None else ''

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
    def bind_nodes(self):
        return self.model_node.findall('{f}bind')

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
    def media_references(self, form, lang=None):
        lang_condition = '[@lang="%s"]' % lang if lang else ''
        nodes = self.itext_node.findall('{f}translation%s/{f}text/{f}value[@form="%s"]' % (lang_condition, form))
        return list(set([str(n.text) for n in nodes]))

    @property
    def odk_intents(self):
        nodes = self.findall('{h}head/{odk}intent')
        return list(set(n.attrib.get('class') for n in nodes))

    def text_references(self, lang=None):
        # Accepts lang param for consistency with image_references, etc.,
        # but current text references aren't language-specific
        nodes = self.findall('{h}head/{odk}intent[@class="org.commcare.dalvik.action.PRINT"]/{f}extra[@key="cc:print_template_reference"]')
        return list(set(n.attrib.get('ref').strip("'") for n in nodes))

    def image_references(self, lang=None):
        return self.media_references("image", lang=lang)

    def audio_references(self, lang=None):
        return self.media_references("audio", lang=lang)

    def video_references(self, lang=None):
        return self.media_references("video", lang=lang) + self.media_references("video-inline", lang=lang)

    def rename_media(self, old_path, new_path):
        update_count = 0
        for node in self.itext_node.findall('{f}translation/{f}text/{f}value'):
            if node.text == old_path:
                node.xml.text = new_path
                update_count += 1
        return update_count

    def _get_instance_ids(self):
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
    def _itext_node_groups(self):
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
        self._itext_node_groups.reset_cache(self)

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
        node_groups = self._itext_node_groups()

        duplicate_dict = defaultdict(list)
        for g in node_groups.values():
            duplicate_dict[g].append(g)

        duplicates = [sorted(g, key=lambda ng: ng.id) for g in duplicate_dict.values() if len(g) > 1]

        for dup in duplicates:
            for group in dup[1:]:
                itext_ref = '{{f}}text[@id="{0}"]'.format(group.id)
                for lang in group.nodes.keys():
                    translation = translations[lang]
                    node = translation.find(itext_ref)
                    translation.remove(node.xml)

        def replace_ref_s(xmlstring, find, replace):
            find = find.encode('utf-8', 'xmlcharrefreplace')
            replace = replace.encode('utf-8', 'xmlcharrefreplace')
            return xmlstring.replace(find, replace)

        xf_string = self.render()
        for dup in duplicates:
            reference = dup[0]
            new_ref = "jr:itext('{0}')".format(reference.id)

            for group in dup[1:]:
                old_ref = 'jr:itext(\'{0}\')'.format(group.id)
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

    def add_missing_instances(self, form, app):
        from corehq.apps.app_manager.suite_xml.post_process.instances import get_all_instances_referenced_in_xpaths
        instance_declarations = self._get_instance_ids()
        missing_unknown_instances = set()
        instances, unknown_instance_ids = get_all_instances_referenced_in_xpaths(
            app, [self.render().decode('utf-8')])

        for instance_id in unknown_instance_ids:
            if instance_id not in instance_declarations:
                missing_unknown_instances.add(instance_id)

        if missing_unknown_instances:
            instance_ids = "', '".join(missing_unknown_instances)
            module = form.get_module()
            raise XFormValidationError(_(
                "The form '{form}' in '{module}' is missing some instance declarations "
                "that can't be automatically added: '{instance_ids}'"
            ).format(form=form.default_name(), module=module.default_name(app), instance_ids=instance_ids))

        for instance in instances:
            if instance.id not in instance_declarations:
                self.add_instance(instance.id, instance.src)

    @requires_itext()
    def rename_language(self, old_code, new_code):
        trans_node = self.translations().get(old_code)
        duplicate_node = self.translations().get(new_code)

        if not trans_node or not trans_node.exists():
            raise XFormException(_("There's no language called '{}'").format(old_code))
        if duplicate_node and duplicate_node.exists():
            raise XFormException(_("There's already a language called '{}'").format(new_code))
        trans_node.attrib['lang'] = new_code

        self._reset_translations_cache()

    def exclude_languages(self, whitelist):
        changes = False
        for lang, trans_node in self.translations().items():
            if lang not in whitelist:
                self.itext_node.remove(trans_node.xml)
                changes = True

        if changes and not len(self.itext_node):
            raise XFormException(_("Form does not contain any translations for any of the build languages"))

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
        node_group = self._itext_node_groups().get(id)
        if not node_group:
            return None

        lang = lang or list(self.translations().keys())[0]
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
                        'Unrecognized value of "form" attribute in \'<value form="{}">\'. '
                        '"form" attribute is optional. Valid values are: "{}".').format(
                            f, '", "'.join(VALID_VALUE_FORMS)
                    ))
            raise XFormException(_('<translation lang="{lang}"><text id="{id}"> node has no <value>').format(
                lang=lang, id=id
            ))

        return text

    def _get_label_translations(self, prompt, langs):
        if prompt.tag_name == 'repeat':
            return self._get_label_translations(prompt.find('..'), langs)
        label_node = prompt.find('{f}label')
        translations = {}
        if label_node.exists() and 'ref' in label_node.attrib:
            for lang in langs:
                label = self.localize(label_node.attrib['ref'], lang)
                if label:
                    translations[lang] = label

        return translations

    def _get_label_text(self, prompt, langs):
        if prompt.tag_name == 'repeat':
            return self._get_label_text(prompt.find('..'), langs)
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

    def _get_label_ref(self, prompt):
        if prompt.tag_name == 'repeat':
            return self._get_label_ref(prompt.find('..'))

        label_node = prompt.find('{f}label')
        if label_node.exists():
            if 'ref' in label_node.attrib:
                return self._normalize_itext_id(label_node.attrib['ref'])
        return None

    def resolve_path(self, path, path_context=""):
        '''
            input: path with type ConditionalCaseUpdate
            output: type str
        '''
        path_str = getattr(path, "question_path", path)
        path_context_str = getattr(path_context, "question_path", path_context)
        if path_str == "":
            return path_context_str
        elif path_str is None:
            raise CaseError("Every case must have a name")
        elif path_str[0] == "/":
            return path_str
        elif not path_context:
            return "/%s/%s" % (self.data_node.tag_name, path_str)
        else:
            return "%s/%s" % (path_context_str, path_str)

    def hashtag_path(self, path):
        path = getattr(path, "question_path", path)
        for hashtag, replaces in hashtag_replacements:
            path = re.sub(replaces, hashtag, path)
        return path

    @requires_itext(list)
    def get_languages(self):
        if not self.exists():
            return []

        return list(self.translations().keys())

    def get_external_instances(self):
        """
        Get a dictionary of all "external" instances, like:
        {
          "country": "jr://fixture/item-list:country"
        }
        """
        def _get_instances():
            return itertools.chain(
                self.model_node.findall('{f}instance'),
                self.model_node.findall('instance')
            )
        instance_nodes = _get_instances()
        instance_dict = {}
        for instance_node in instance_nodes:
            instance_id = instance_node.attrib.get('id')
            src = instance_node.attrib.get('src')
            if instance_id and src:
                instance_dict[instance_id] = src
        return instance_dict

    def get_questions(self, langs, include_triggers=False,
                      include_groups=False, include_translations=False,
                      exclude_select_with_itemsets=False, include_fixtures=False):
        """
        parses out the questions from the xform, into the format:
        [{"label": label, "tag": tag, "value": value}, ...]

        if the xform is bad, it will raise an XFormException

        :param langs: A list of language codes - will use the first available language code in
            determining the question's "label". When include_translations=True, it will attempt to
            find a translation for each language in langs, though will only add it if non-null.
        :param include_triggers: When set to True will return label questions as well as regular questions
        :param include_groups: When set will return repeats and group questions
        :param include_translations: When set to True will return all the translations for the question
        :param exclude_select_with_itemsets: exclude select/multi-select with itemsets
        :param include_fixtures: add fixture data for questions that we can infer it from
        """
        # HELPME
        #
        # This method has been flagged for refactoring due to its complexity and
        # frequency of touches in changesets
        #
        # If you are writing code that touches this method, your changeset
        # should leave the method better than you found it.
        #
        # Please remove this flag when this method no longer triggers an 'E' or 'F'
        # classification from the radon code static analysis

        from corehq.apps.app_manager.models import ConditionalCaseUpdate
        from corehq.apps.app_manager.util import first_elem, extract_instance_id_from_nodeset_ref

        def _get_select_question_option(item):
            translation = self._get_label_text(item, langs)
            try:
                value = item.findtext('{f}value').strip()
            except AttributeError:
                raise XFormException(_("<item> ({}) has no <value>").format(translation))
            option = {
                'label': translation,
                'label_ref': self._get_label_ref(item),
                'value': value,
            }
            if include_translations:
                option['translations'] = self._get_label_translations(item, langs)
            return option

        if not self.exists():
            return []

        questions = []

        # control_nodes will contain all nodes in question tree (the <h:body> of an xform)
        # The question tree doesn't contain every question - notably, it's missing hidden values - so
        # we also need to look at the data tree (the <model> in the xform's <head>). Getting the leaves
        # of the data tree should be sufficient to fill in what's not available from the question tree.
        control_nodes = self._get_control_nodes()
        leaf_data_nodes = self._get_leaf_data_nodes()
        external_instances = self.get_external_instances()

        for cnode in control_nodes:
            node = cnode.node
            path = cnode.path

            path = getattr(path, "question_path", path)

            is_group = not cnode.is_leaf
            if is_group and not include_groups:
                continue

            if node.tag_name == 'trigger'and not include_triggers:
                continue

            if (exclude_select_with_itemsets and cnode.data_type in ['Select', 'MSelect']
                    and cnode.node.find('{f}itemset').exists()):
                continue
            question = {
                "label": self._get_label_text(node, langs),
                "label_ref": self._get_label_ref(node),
                "tag": node.tag_name,
                "value": path,
                "repeat": cnode.repeat,
                "group": cnode.group,
                "type": cnode.data_type,
                "relevant": cnode.relevant,
                "required": cnode.required == "true()",
                "constraint": cnode.constraint,
                "comment": self._get_comment(path),
                "hashtagValue": self.hashtag_path(path),
                "setvalue": self._get_setvalue(path),
                "is_group": is_group,
            }
            if include_translations:
                question["translations"] = self._get_label_translations(node, langs)

            if include_fixtures and cnode.node.find('{f}itemset').exists():
                itemset_node = cnode.node.find('{f}itemset')
                nodeset = itemset_node.attrib.get('nodeset')
                fixture_data = {
                    'nodeset': nodeset,
                }
                if itemset_node.find('{f}label').exists():
                    fixture_data['label_ref'] = itemset_node.find('{f}label').attrib.get('ref')
                if itemset_node.find('{f}value').exists():
                    fixture_data['value_ref'] = itemset_node.find('{f}value').attrib.get('ref')

                fixture_id = extract_instance_id_from_nodeset_ref(nodeset)
                if fixture_id:
                    fixture_data['instance_id'] = fixture_id
                    fixture_data['instance_ref'] = external_instances.get(fixture_id)

                question['data_source'] = fixture_data

            if cnode.items is not None:
                question['options'] = [_get_select_question_option(item) for item in cnode.items]

            constraint_ref_xml = '{jr}constraintMsg'
            if cnode.constraint and cnode.bind_node.attrib.get(constraint_ref_xml):
                constraint_jr_itext = cnode.bind_node.attrib.get(constraint_ref_xml)
                question['constraintMsg_ref'] = self._normalize_itext_id(constraint_jr_itext)

            questions.append(question)

        repeat_contexts = set()
        group_contexts = set()
        excluded_paths = set()  # prevent adding the same question twice
        for cnode in control_nodes:
            excluded_paths.add(cnode.path)
            if cnode.repeat is not None:
                repeat_contexts.add(cnode.repeat)
            if cnode.data_type == 'Repeat':
                # A repeat is a node inside of a `group`, so it part of both a
                # repeat and a group context
                repeat_contexts.add(cnode.path)
                group_contexts.add(cnode.path)
            if cnode.group is not None:
                group_contexts.add(cnode.group)
            if cnode.data_type == 'Group':
                group_contexts.add(cnode.path)

        repeat_contexts = sorted(repeat_contexts, reverse=True)
        group_contexts = sorted(group_contexts, reverse=True)

        save_to_case_nodes = {}
        for path, data_node in leaf_data_nodes.items():
            if isinstance(path, ConditionalCaseUpdate):
                path = path.question_path
            if path not in excluded_paths:
                bind = self.get_bind(path)

                matching_repeat_context = first_elem([rc for rc in repeat_contexts
                                                      if path.startswith(rc + '/')])
                matching_group_context = first_elem([gc for gc in group_contexts
                                                     if path.startswith(gc + '/')])

                question = {
                    "tag": "hidden",
                    "value": path,
                    "repeat": matching_repeat_context,
                    "group": matching_group_context,
                    "type": "DataBindOnly",
                    "calculate": bind.attrib.get('calculate') if hasattr(bind, 'attrib') else None,
                    "relevant": bind.attrib.get('relevant') if hasattr(bind, 'attrib') else None,
                    "constraint": bind.attrib.get('constraint') if hasattr(bind, 'attrib') else None,
                    "comment": self._get_comment(path),
                    "setvalue": self._get_setvalue(path)
                }

                # Include meta information about the stock entry
                if data_node.tag_name == 'entry':
                    parent = next(data_node.xml.iterancestors())
                    if len(parent):
                        is_stock_element = any([namespace == COMMTRACK_REPORT_XMLNS for namespace in parent.nsmap.values()])
                        if is_stock_element:
                            question.update({
                                "stock_entry_attributes": dict(data_node.xml.attrib),
                                "stock_type_attributes": dict(parent.attrib),
                            })
                if '/case/' in path:
                    path_to_case = path.split('/case/')[0] + '/case'
                    save_to_case_nodes[path_to_case] = {
                        'data_node': data_node,
                        'repeat': matching_repeat_context,
                        'group': matching_group_context,
                    }

                hashtag_path = self.hashtag_path(path)
                question.update({
                    "label": hashtag_path,
                    "hashtagValue": hashtag_path,
                })

                if include_translations:
                    question["translations"] = {}

                questions.append(question)

        for path, node_info in save_to_case_nodes.items():
            data_node = node_info['data_node']
            try:
                case_node = next(data_node.iterancestors('{cx2}case'))
                for attrib in ('case_id', 'user_id', 'date_modified'):
                    if attrib not in case_node.attrib:
                        continue

                    bind = self.get_bind(path + '/@' + attrib)
                    question = {
                        "tag": "hidden",
                        "value": '{}/@{}'.format(path, attrib),
                        "repeat": node_info['repeat'],
                        "group": node_info['group'],
                        "type": "DataBindOnly",
                        "calculate": None,
                        "relevant": None,
                        "constraint": None,
                        "comment": None,
                    }
                    if bind.exists():
                        question.update({
                            "calculate": bind.attrib.get('calculate') if hasattr(bind, 'attrib') else None,
                            "relevant": bind.attrib.get('relevant') if hasattr(bind, 'attrib') else None,
                            "constraint": bind.attrib.get('constraint') if hasattr(bind, 'attrib') else None,
                        })
                    else:
                        ref = self.model_node.find('{f}setvalue[@ref="%s"]' % path)
                        if ref.exists():
                            question.update({
                                'calculate': ref.attrib.get('value'),
                            })

                    hashtag_path = '{}/@{}'.format(self.hashtag_path(path), attrib)
                    question.update({
                        "label": hashtag_path,
                        "hashtagValue": hashtag_path,
                    })

                    if include_translations:
                        question["translations"] = {}

                    questions.append(question)
            except StopIteration:
                pass

        return questions

    def _get_control_nodes(self):
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
                    path = self.resolve_path(self._get_path(node), path_context)
                    bind = self.get_bind(path)
                    data_type = _infer_vellum_type(node, bind)
                    relevant = bind.attrib.get('relevant') if bind else None
                    required = bind.attrib.get('required') if bind else None
                    constraint = bind.attrib.get('constraint') if bind else None
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
                        control_nodes.append(ControlNode(
                            node=node,
                            bind_node=bind,
                            path=path,
                            repeat=repeat_context,
                            group=group_context,
                            items=items,
                            is_leaf=is_leaf,
                            data_type=data_type,
                            relevant=relevant,
                            required=required,
                            constraint=constraint,
                        ))
                    if recursive_kwargs:
                        for_each_control_node(**recursive_kwargs)

        for_each_control_node(self.find('{h}body'))
        return control_nodes

    def _get_comment(self, path):
        try:
            return self._get_flattened_data_nodes()[path].attrib.get('{v}comment')
        except KeyError:
            return None

    def _get_setvalue(self, path):
        try:
            return self.model_node.find('{f}setvalue[@ref="%s"]' % path).attrib['value']
        except (KeyError, AttributeError):
            return None

    def _get_path(self, node):
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
            raise XFormException(_("Node <{}> has no 'ref' or 'bind'").format(node.tag_name))
        return path

    def _get_leaf_data_nodes(self):
        return self._get_flattened_data_nodes(leaves_only=True)

    @memoized
    def _get_flattened_data_nodes(self, leaves_only=False):
        if not self.exists():
            return {}

        data_nodes = {}

        def for_each_data_node(parent, path_context=""):
            children = parent.findall('*')
            for child in children:
                path = self.resolve_path(child.tag_name, path_context)
                for_each_data_node(child, path_context=path)
            if (not leaves_only or not children) and path_context:
                data_nodes[path_context] = parent

        for_each_data_node(self.data_node)
        return data_nodes

    def add_case_and_meta(self, form):
        form.get_app().assert_app_v2()
        self._create_casexml(form)
        self._add_usercase(form)
        self._add_meta_2(form)

    def add_case_and_meta_advanced(self, form):
        self._create_casexml_advanced(form)
        self._add_meta_2(form)

    def already_has_meta(self):
        meta_blocks = set()
        for meta_xpath in ('{orx}meta', '{x}meta', '{orx}Meta', '{x}Meta'):
            meta = self.data_node.find(meta_xpath)
            if meta.exists():
                meta_blocks.add(meta)

        return meta_blocks

    def _add_usercase_bind(self, usercase_path):
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

    def _add_usercase(self, form):
        usercase_path = 'commcare_usercase/'
        actions = form.active_actions()

        if 'usercase_update' in actions and actions['usercase_update'].update:
            self._add_usercase_bind(usercase_path)
            usercase_block = _make_elem('{x}commcare_usercase')
            case_block = XFormCaseBlock(self, usercase_path)
            case_block.add_case_updates(actions['usercase_update'].update,
                save_only_if_edited=self.save_only_if_edited)
            usercase_block.append(case_block.elem)
            self.data_node.append(usercase_block)

        if 'usercase_preload' in actions and actions['usercase_preload'].preload:
            self.add_case_preloads(
                actions['usercase_preload'].preload,
                case_id_xpath=SESSION_USERCASE_ID
            )

    def _add_meta_2(self, form):
        case_parent = self.data_node
        app = form.get_app()
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
            '{orx}drift',
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
        self.add_setvalue(
            ref="meta/drift",
            event="xforms-revalidate",
            value="if(count(instance('commcaresession')/session/context/drift) = 1, "
                  "instance('commcaresession')/session/context/drift, '')",
        )

        # never add pollsensor to a pre-2.14 app
        if app.enable_auto_gps:
            if form.get_auto_gps_capture():
                self._add_pollsensor(ref=self.resolve_path("meta/location"))
            elif self.model_node.findall("{f}bind[@type='geopoint']"):
                self._add_pollsensor()

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
        from corehq.apps.app_manager.models import ConditionalCaseUpdate
        if d.get('relevant') == 'true()':
            del d['relevant']
        d['nodeset'] = self.resolve_path(d['nodeset'])
        if 'calculate' in d and isinstance(d['calculate'], ConditionalCaseUpdate):
            d['calculate'] = d['calculate'].question_path
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

    def _add_pollsensor(self, event="xforms-ready", ref=None):
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
                template = "selected({path}, '{answer}')"
            elif condition.operator == 'boolean_true':
                template = "{path}"
            else:
                template = "{path} = '{answer}'"
            return template.format(
                path=self.resolve_path(condition.question),
                answer=condition.answer
            )
        else:
            return 'false()'

    def _create_casexml(self, form):
        # HELPME
        #
        # This method has been flagged for refactoring due to its complexity and
        # frequency of touches in changesets
        #
        # If you are writing code that touches this method, your changeset
        # should leave the method better than you found it.
        #
        # Please remove this flag when this method no longer triggers an 'E' or 'F'
        # classification from the radon code static analysis

        actions = form.active_actions()

        form_opens_case = 'open_case' in actions
        if form.requires == 'none' and not form_opens_case and 'update_case' in actions:
            raise CaseError("To update a case you must either open a case or require a case to begin with")

        module = form.get_module()
        if form.get_module().is_multi_select():
            self.add_instance(
                'selected_cases',
                'jr://instance/selected-entities/selected_cases'
            )
            default_case_management = False
        else:
            default_case_management = not _module_loads_registry_case(module)
        default_case_management = default_case_management or form_opens_case
        delegation_case_block = None
        if not actions or (form.requires == 'none' and not form_opens_case):
            case_block = None
        else:
            case_block = XFormCaseBlock(self)
            if form.requires != 'none':
                def make_delegation_stub_case_block():
                    path = 'cc_delegation_stub/'
                    DELEGATION_ID = 'delegation_id'
                    outer_block = _make_elem('{x}cc_delegation_stub', {DELEGATION_ID: ''})
                    delegation_case_block = XFormCaseBlock(self, path)
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

            case_id_xpath = get_add_case_preloads_case_id_xpath(module, form)
            if form_opens_case:
                open_case_action = actions['open_case']
                case_block.add_create_block(
                    relevance=self.action_relevance(open_case_action.condition),
                    case_name=open_case_action.name_update.question_path,
                    case_type=form.get_case_type(),
                    autoset_owner_id=autoset_owner_id_for_open_case(actions),
                    has_case_sharing=form.get_app().case_sharing,
                    case_id=case_id_xpath
                )
                if 'external_id' in actions['open_case'] and actions['open_case'].external_id:
                    case_block.add_case_updates(
                        {'external_id': actions['open_case'].external_id},
                        save_only_if_edited=self.save_only_if_edited
                    )
            elif default_case_management:
                case_block.bind_case_id(case_id_xpath)

            if 'update_case' in actions and default_case_management:
                self._add_case_updates(
                    case_block,
                    getattr(actions.get('update_case'), 'update', {}),
                    # case_id_xpath is set based on an assumption about the way suite_xml.py determines the
                    # case_id. If suite_xml changes the way it sets case_id for case updates, this will break.
                    case_id_xpath=case_id_xpath
                )

            if 'close_case' in actions and default_case_management:
                case_block.add_close_block(self.action_relevance(actions['close_case'].condition))

            if 'case_preload' in actions:
                self.add_case_preloads(
                    actions['case_preload'].preload,
                    # (As above) case_id_xpath is set based on an assumption about the way suite_xml.py determines
                    # the case_id. If suite_xml changes the way it sets case_id for case updates, this will break.
                    case_id_xpath=case_id_xpath
                )

        if 'subcases' in actions and default_case_management:
            subcases = actions['subcases']

            repeat_context_count = form.actions.count_subcases_per_repeat_context()
            for subcase in subcases:
                if not form.get_app().case_type_exists(subcase.case_type):
                    raise CaseError("Case type (%s) for form (%s) does not exist" % (
                        subcase.case_type, form.default_name()
                    ))
                if subcase.repeat_context:
                    base_path = '%s/' % subcase.repeat_context
                    parent_node = self.instance_node.find(
                        '/{x}'.join(subcase.repeat_context.split('/'))[1:]
                    )
                    nest = repeat_context_count[subcase.repeat_context] > 1
                    case_id = 'uuid()'
                else:
                    base_path = ''
                    parent_node = self.data_node
                    nest = True
                    case_id = session_var(form.session_var_for_action(subcase))

                if nest:
                    subcase_node = _make_elem('{x}%s' % subcase.form_element_name)
                    parent_node.append(subcase_node)
                    path = '%s%s/' % (base_path, subcase.form_element_name)
                else:
                    subcase_node = parent_node
                    path = base_path

                subcase_block = XFormCaseBlock(self, path)
                subcase_node.insert(0, subcase_block.elem)
                subcase_block.add_create_block(
                    relevance=self.action_relevance(subcase.condition),
                    case_name=subcase.name_update.question_path,
                    case_type=subcase.case_type,
                    delay_case_id=bool(subcase.repeat_context),
                    autoset_owner_id=autoset_owner_id_for_subcase(subcase),
                    has_case_sharing=form.get_app().case_sharing,
                    case_id=case_id
                )

                subcase_block.add_case_updates(subcase.case_properties,
                    save_only_if_edited=self.save_only_if_edited)

                if subcase.close_condition.is_active():
                    subcase_block.add_close_block(self.action_relevance(subcase.close_condition))

                index_same_casetype = not DONT_INDEX_SAME_CASETYPE.enabled(self.domain)
                if case_block is not None and (index_same_casetype or subcase.case_type != form.get_case_type()):
                    reference_id = subcase.reference_id or 'parent'

                    subcase_block.add_index_ref(
                        reference_id,
                        form.get_case_type(),
                        self.resolve_path("case/@case_id"),
                    )

        case = self.case_node
        case_parent = self.data_node

        if case_block is not None and not case_block.is_empty:
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
            name = "next_{}".format(form.schedule_form_id)
            forms_due.append("/data/{}".format(name))

            self.add_instance(
                form_xpath.fixture_id,
                'jr://fixture/{}'.format(form_xpath.fixture_id)
            )

            if form.get_phase().id == 1:
                self.add_bind(
                    nodeset='/data/{}'.format(name),
                    calculate=form_xpath.first_visit_phase_set
                )
            else:
                self.add_bind(
                    nodeset='/data/{}'.format(name),
                    calculate=form_xpath.xpath_phase_set
                )

            self.data_node.append(_make_elem(name))

        self.add_bind(
            nodeset='/data/{}'.format(SCHEDULE_GLOBAL_NEXT_VISIT_DATE),
            calculate='date(min({}))'.format(','.join(forms_due))
        )
        self.data_node.append(_make_elem(SCHEDULE_GLOBAL_NEXT_VISIT_DATE))

        self.add_bind(
            nodeset='/data/{}'.format(SCHEDULE_NEXT_DUE),
            calculate=QualifiedScheduleFormXPath.next_visit_date(forms, case)
        )
        self.data_node.append(_make_elem(SCHEDULE_NEXT_DUE))

    def _create_casexml_advanced(self, form):
        self._scheduler_case_updates_populated = True
        from corehq.apps.app_manager.util import split_path

        if not form.actions.get_all_actions():
            return

        def configure_visit_schedule_updates(update_block, action, session_case_id):
            case = session_case_id.case()
            schedule_form_xpath = QualifiedScheduleFormXPath(form, form.get_phase(), form.get_module(), case)

            self.add_instance(
                schedule_form_xpath.fixture_id,
                'jr://fixture/{}'.format(schedule_form_xpath.fixture_id)
            )

            self.add_bind(
                nodeset='{}/case/update/{}'.format(action.form_element_name, SCHEDULE_PHASE),
                type="xs:integer",
                calculate=schedule_form_xpath.current_schedule_phase_calculation(
                    self.action_relevance(form.schedule.termination_condition),
                    self.action_relevance(form.schedule.transition_condition),
                )
            )
            update_block.append(make_case_elem(SCHEDULE_PHASE))
            self._add_scheduler_case_update(action.case_type, SCHEDULE_PHASE)

            self.add_bind(
                nodeset='/data/{}'.format(SCHEDULE_CURRENT_VISIT_NUMBER),
                calculate=schedule_form_xpath.next_visit_due_num
            )
            self.data_node.append(_make_elem(SCHEDULE_CURRENT_VISIT_NUMBER))

            self.add_bind(
                nodeset='/data/{}'.format(SCHEDULE_UNSCHEDULED_VISIT),
                calculate=schedule_form_xpath.is_unscheduled_visit,
            )
            self.data_node.append(_make_elem(SCHEDULE_UNSCHEDULED_VISIT))

            last_visit_num = SCHEDULE_LAST_VISIT.format(form.schedule_form_id)
            self.add_bind(
                nodeset='{}/case/update/{}'.format(action.form_element_name, last_visit_num),
                relevant="not(/data/{})".format(SCHEDULE_UNSCHEDULED_VISIT),
                calculate="/data/{}".format(SCHEDULE_CURRENT_VISIT_NUMBER),
            )
            update_block.append(make_case_elem(last_visit_num))
            self._add_scheduler_case_update(action.case_type, last_visit_num)

            last_visit_date = SCHEDULE_LAST_VISIT_DATE.format(form.schedule_form_id)
            self.add_bind(
                nodeset='{}/case/update/{}'.format(action.form_element_name, last_visit_date),
                type="xsd:dateTime",
                calculate=self.resolve_path("meta/timeEnd"),
                relevant="not(/data/{})".format(SCHEDULE_UNSCHEDULED_VISIT),
            )
            update_block.append(make_case_elem(last_visit_date))
            self._add_scheduler_case_update(action.case_type, last_visit_date)

            self._schedule_global_next_visit_date(form, case)

        def create_case_block(action, bind_case_id_xpath=None):
            tag = action.form_element_name
            path = tag + '/'
            base_node = _make_elem("{{x}}{0}".format(tag))
            self.data_node.append(base_node)
            case_block = XFormCaseBlock(self, path=path)
            if bind_case_id_xpath:
                case_block.bind_case_id(bind_case_id_xpath, path)

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
                getattr(meta.action, 'case_tag', None): meta.id
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
                    self._add_case_updates(
                        update_case_block,
                        action.case_properties,
                        base_node_path=path,
                        case_id_xpath=session_case_id)

                if action.close_condition.type != 'never':
                    update_case_block.add_close_block(self.action_relevance(action.close_condition))

                if has_schedule and action == last_real_action:
                    self.add_casedb()
                    configure_visit_schedule_updates(update_case_block.update_block, action, session_case_id)

        repeat_context_count = form.actions.count_subcases_per_repeat_context()

        def get_action_path(action, create_subcase_node=True):
            if action.repeat_context:
                base_path = '%s/' % action.repeat_context
                parent_node = self.instance_node.find(
                    '/{x}'.join(action.repeat_context.split('/'))[1:]
                )
                nest = repeat_context_count[action.repeat_context] > 1
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

            open_case_block = XFormCaseBlock(self, path)
            subcase_node.insert(0, open_case_block.elem)
            open_case_block.add_create_block(
                relevance=self.action_relevance(action.open_condition),
                case_name=action.name_update.question_path,
                case_type=action.case_type,
                delay_case_id=bool(action.repeat_context),
                autoset_owner_id=autoset_owner_id_for_advanced_action(action),
                has_case_sharing=form.get_app().case_sharing,
                case_id=case_id
            )

            if action.case_properties:
                open_case_block.add_case_updates(action.case_properties,
                    save_only_if_edited=self.save_only_if_edited)

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

                if case_index.relationship == 'question':
                    self.add_bind(
                        nodeset="{path}case/index/{ref}/@relationship".format(path=path, ref=reference_id),
                        calculate=self.resolve_path(case_index.relationship_question),
                    )
                    self.add_bind(
                        nodeset="%scase/create/owner_id" % path,
                        calculate=XPath.if_(XPath(case_index.relationship_question).eq(XPath.string('extension')),
                                            XPath.string(UNOWNED_EXTENSION_OWNER_ID),
                                            self.resolve_path("meta/userID")),
                    )

            if action.close_condition.type != 'never':
                open_case_block.add_close_block(self.action_relevance(action.close_condition))

    def add_casedb(self):
        if not self.has_casedb:
            self.add_instance('casedb', src='jr://instance/casedb')
            self.has_casedb = True

    def _add_case_updates(self, case_block, updates, base_node_path=None, case_id_xpath=None):
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
        if '' in updates_by_case:
            # 90% use-case
            basic_updates = updates_by_case.pop('')
            if basic_updates:
                case_block.add_case_updates(basic_updates, save_only_if_edited=self.save_only_if_edited)
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
                parent_case_block = XFormCaseBlock.make_parent_case_block(
                    self,
                    node_path,
                    parent_path,
                    case_id_xpath=case_id_xpath)
                parent_case_block.add_case_updates(updates, save_only_if_edited=self.save_only_if_edited)
                node.append(parent_case_block.elem)

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
        'icon': 'fcc fcc-fd-android-intent',
        'editable': True,
    },
    "Audio": {
        'tag': 'upload',
        'media': 'audio/*',
        'type': 'binary',
        'icon': 'fcc fcc-fd-audio-capture',
    },
    "Barcode": {
        'tag': 'input',
        'type': 'barcode',
        'icon': 'fcc fcc-fd-android-intent',
        'editable': True,
    },
    "DataBindOnly": {
        'icon': 'fcc fcc-fd-variable',
        'editable': True,
    },
    "Date": {
        'tag': 'input',
        'type': 'xsd:date',
        'icon': 'fa-solid fa-calendar-days',
        'editable': True,
    },
    "DateTime": {
        'tag': 'input',
        'type': 'xsd:dateTime',
        'icon': 'fcc fcc-fd-datetime',
        'editable': True,
    },
    "Double": {
        'tag': 'input',
        'type': 'xsd:double',
        'icon': 'fcc fcc-fd-decimal',
        'editable': True,
    },
    "FieldList": {
        'tag': 'group',
        'appearance': 'field-list',
        'icon': 'fa fa-bars',
    },
    "Geopoint": {
        'tag': 'input',
        'type': 'geopoint',
        'icon': 'fa-solid fa-location-dot',
        'editable': True,
    },
    "Group": {
        'tag': 'group',
        'icon': 'fa fa-folder-open',
    },
    "Image": {
        'tag': 'upload',
        'media': 'image/*',
        'type': 'binary',
        'icon': 'fa fa-camera',
    },
    "Int": {
        'tag': 'input',
        'type': ('xsd:int', 'xsd:integer'),
        'icon': 'fcc fcc-fd-numeric',
        'editable': True,
    },
    "Long": {
        'tag': 'input',
        'type': 'xsd:long',
        'icon': 'fcc fcc-fd-long',
        'editable': True,
    },
    "MSelect": {
        'tag': 'select',
        'icon': 'fcc fcc-fd-multi-select',
        'editable': True,
    },
    "PhoneNumber": {
        'tag': 'input',
        'type': ('xsd:string', None),
        'appearance': 'numeric',
        'icon': 'fa fa-signal',
        'editable': True,
    },
    "Repeat": {
        'tag': 'repeat',
        'icon': 'fa fa-retweet',
    },
    "SaveToCase": {
        'tag': 'save_to_case',
        'icon': 'fa fa-save',
    },

    "Secret": {
        'tag': 'secret',
        'type': ('xsd:string', None),
        'icon': 'fa fa-key',
        'editable': True,
    },
    "Select": {
        'tag': 'select1',
        'icon': 'fcc fcc-fd-single-select',
        'editable': True,
    },
    "Text": {
        'tag': 'input',
        'type': ('xsd:string', None),
        'icon': 'fcc fcc-fd-text',
        'editable': True,
    },
    "Time": {
        'tag': 'input',
        'type': 'xsd:time',
        'icon': 'fa-regular fa-clock',
        'editable': True,
    },
    "Trigger": {
        'tag': 'trigger',
        'icon': 'fa fa-tag',
    },
    "Video": {
        'tag': 'upload',
        'media': 'video/*',
        'type': 'binary',
        'icon': 'fa fa-video-camera',
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
    [{field: value for field, value in (list(dct.items()) + [('name', key)])}
     for key, dct in VELLUM_TYPES.items()],
    ('tag', 'type', 'media', 'appearance')
)


def _infer_vellum_type(control, bind):
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


def _module_loads_registry_case(module):
    """Local function to allow mocking in tests"""
    from .util import module_loads_registry_case
    return module_loads_registry_case(module)
