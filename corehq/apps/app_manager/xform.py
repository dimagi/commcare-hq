from collections import defaultdict, OrderedDict
from functools import wraps
import logging
from casexml.apps.case.xml import V2_NAMESPACE
from corehq.apps.app_manager.const import APP_V1, SCHEDULE_PHASE, SCHEDULE_LAST_VISIT, SCHEDULE_LAST_VISIT_DATE, \
    CASE_ID, USERCASE_ID, USERCASE_PREFIX
from lxml import etree as ET
from corehq.util.view_utils import get_request
from dimagi.utils.decorators.memoized import memoized
from .xpath import CaseIDXPath, session_var, CaseTypeXpath
from .exceptions import XFormException, CaseError, XFormValidationError, BindNotFound
import formtranslate.api


def parse_xml(string):
    # Work around: ValueError: Unicode strings with encoding
    # declaration are not supported.
    if isinstance(string, unicode):
        string = string.encode("utf-8")
    try:
        return ET.fromstring(string, parser=ET.XMLParser(encoding="utf-8", remove_comments=True))
    except ET.ParseError, e:
        raise XFormException("Error parsing XML" + (": %s" % str(e)))


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
)


def _make_elem(tag, attr=None):
    attr = attr or {}
    return ET.Element(tag.format(**namespaces), dict([(key.format(**namespaces), val) for key,val in attr.items()]))


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
            raise Exception("Group already has node for lang: {0}".format(node.lang))
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
            elif key.startswith(USERCASE_PREFIX):
                # Skip usercase keys. They are handled by the usercase block.
                # cf. add_usercase
                continue
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

    def add_index_ref(self, reference_id, case_type, ref):
        index_node = self.elem.find('{cx2}index'.format(**namespaces))
        if index_node is None:
            index_node = make_case_elem('index')
            self.elem.append(index_node)
        parent_index = make_case_elem(reference_id, {'case_type': case_type})
        index_node.append(parent_index)

        self.xform.add_bind(
            nodeset='{path}case/index/{ref}'.format(path=self.path, ref=reference_id),
            calculate=ref,
        )

def autoset_owner_id_for_open_case(actions):
    return not ('update_case' in actions and
                'owner_id' in actions['update_case'].update)


def autoset_owner_id_for_subcase(subcase):
    return 'owner_id' not in subcase.case_properties


def validate_xform(source, version='1.0'):
    if isinstance(source, unicode):
        source = source.encode("utf-8")
    # normalize and strip comments
    source = ET.tostring(parse_xml(source))
    validation_results = formtranslate.api.validate(source, version=version)
    if not validation_results.success:
        raise XFormValidationError(
            fatal_error=validation_results.fatal_error,
            version=version,
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

    def __str__(self):
        return ET.tostring(self.xml) if self.xml is not None else ''

    def validate(self, version='1.0'):
        validate_xform(ET.tostring(self.xml) if self.xml is not None else '',
                       version=version)
        return self

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

    @property
    def image_references(self):
        return self.media_references(form="image")

    @property
    def audio_references(self):
        return self.media_references(form="audio")

    @property
    def video_references(self):
        return self.media_references(form="video")

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

    @requires_itext()
    def rename_language(self, old_code, new_code):
        trans_node = self.translations().get(old_code)
        duplicate_node = self.translations().get(new_code)

        if not trans_node or not trans_node.exists():
            raise XFormException("There's no language called '%s'" % old_code)
        if duplicate_node and duplicate_node.exists():
            raise XFormException("There's already a language called '%s'" % new_code)
        trans_node.attrib['lang'] = new_code

        self._reset_translations_cache()

    def exclude_languages(self, whitelist):
        changes = False
        for lang, trans_node in self.translations().items():
            if lang not in whitelist:
                self.itext_node.remove(trans_node.xml)
                changes = True

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
            raise XFormException('<translation lang="%s"><text id="%s"> node has no <value>' % (
                lang, id
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

    @requires_itext(list)
    def get_languages(self):
        if not self.exists():
            return []

        return self.translations().keys()

    def get_questions(self, langs, include_triggers=False,
                      include_groups=False, include_translations=False):
        """
        parses out the questions from the xform, into the format:
        [{"label": label, "tag": tag, "value": value}, ...]

        if the xform is bad, it will raise an XFormException

        """

        if not self.exists():
            return []

        questions = []
        repeat_contexts = set()
        excluded_paths = set()

        control_nodes = self.get_control_nodes()

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
                "required": required == "true()"
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
                        raise XFormException("<item> (%r) has no <value>" % translation)
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

        for data_node, path in self.get_leaf_data_nodes():
            if path not in excluded_paths:
                bind = self.get_bind(path)
                try:
                    matching_repeat_context = [
                        rc for rc in repeat_contexts if path.startswith(rc)
                    ][0]
                except IndexError:
                    matching_repeat_context = None
                question = {
                    "label": path,
                    "tag": "hidden",
                    "value": path,
                    "repeat": matching_repeat_context,
                    "group": matching_repeat_context,
                    "type": "DataBindOnly",
                    "calculate": bind.attrib.get('calculate') if hasattr(bind, 'attrib') else None,
                }
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
            raise XFormException("Node <%s> has no 'ref' or 'bind'" % node.tag_name)
        return path
    
    def get_leaf_data_nodes(self):
        if not self.exists():
            return []
       
        data_nodes = []

        def for_each_data_node(parent, path_context=""):
            for child in parent.findall('*'):
                path = self.resolve_path(child.tag_name, path_context)
                for_each_data_node(child, path_context=path)
            if not parent.findall('*'):
                data_nodes.append((parent, path_context))

        for_each_data_node(self.data_node)
        return data_nodes

    def add_case_and_meta(self, form):
        if form.get_app().application_version == APP_V1:
            self.add_case_and_meta_1(form)
        else:
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

    def _add_usercase_bind(self, usercase_path):
        self.add_bind(
            nodeset=usercase_path + 'case/@case_id',
            calculate=SESSION_USERCASE_ID,
        )

    def add_usercase(self, form):
        from corehq.apps.app_manager.util import split_path, get_usercase_keys, get_usercase_values

        usercase_path = 'usercase/'
        actions = form.active_actions()

        if 'update_case' in actions:
            usercase_updates = get_usercase_keys(actions['update_case'].update.items())
            if usercase_updates:
                self._add_usercase_bind(usercase_path)
                usercase_block = _make_elem('{x}usercase')
                case_block = CaseBlock(self, usercase_path)
                case_block.add_update_block(usercase_updates)
                usercase_block.append(case_block.elem)
                self.data_node.append(usercase_block)

        if 'case_preload' in actions:
            self.add_casedb()
            usercase_preloads = get_usercase_values(actions['case_preload'].preload.items())
            for nodeset, property_ in usercase_preloads.items():
                parent_path, property_ = split_path(property_)
                property_xpath = {
                    'name': 'case_name',
                    'owner_id': '@owner_id'
                }.get(property_, property_)

                id_xpath = get_case_parent_id_xpath(parent_path, case_id_xpath=SESSION_USERCASE_ID)
                self.add_setvalue(
                    ref=nodeset,
                    value=id_xpath.case().property(property_xpath),
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
                self.add_pollsensor(ref="/data/meta/location")
            elif self.model_node.findall("{f}bind[@type='geopoint']"):
                self.add_pollsensor()

    def add_case_and_meta_1(self, form):
        case = self.case_node

        case_parent = self.data_node
        bind_parent = self.model_node

        casexml, binds, transformation = self.create_casexml_1(form)
        if casexml:
            if case.exists():
                case_parent.remove(case.xml)
            # casexml has to be valid, 'cuz *I* made it
            casexml = parse_xml(casexml)
            case_parent.append(casexml)
            # if DEBUG: tree = ET.fromstring(ET.tostring(tree))
            for bind in bind_parent.findall('{f}bind'):
                if bind.attrib['nodeset'].startswith('case/'):
                    bind_parent.remove(bind.xml)
            for bind in binds:
#                if DEBUG:
#                    xpath = ".//{x}" + bind.attrib['nodeset'].replace("/", "/{x}")
#                    if tree.find(fmt(xpath)) is None:
#                        raise Exception("Invalid XPath Expression %s" % xpath)
                conflicting = bind_parent.find('{f}bind[@nodeset="%s"]' % bind.attrib['nodeset'])
                if conflicting.exists():
                    for a in bind.attrib:
                        conflicting.attrib[a] = bind.attrib[a]
                else:
                    bind_parent.append(bind)

        if not case_parent.exists():
            raise XFormException("Couldn't get the case XML from one of your forms. "
                             "A common reason for this is if you don't have the "
                             "xforms namespace defined in your form. Please verify "
                             'that the xmlns="http://www.w3.org/2002/xforms" '
                             "attribute exists in your form.")

        # Test all of the possibilities so that we don't end up with two "meta" blocks
        for meta in self.already_has_meta():
            case_parent.remove(meta.xml)

        def add_meta():
            orx = namespaces['orx'][1:-1]
            nsmap = {"orx": orx}
            meta = ET.Element("{orx}meta".format(**namespaces), nsmap=nsmap)
            for tag in ('deviceID','timeStart', 'timeEnd','username','userID','instanceID'):
                meta.append(ET.Element(("{orx}%s"%tag).format(**namespaces), nsmap=nsmap))
            case_parent.append(meta)
            id = form.get_unique_id() + "meta"
            binds = [
                {"id": "%s1" % id, "nodeset": "meta/deviceID", "type": "xsd:string", "{jr}preload": "property", "{jr}preloadParams": "DeviceID"},
                {"id": "%s2" % id, "nodeset": "meta/timeStart", "type": "xsd:dateTime", "{jr}preload": "timestamp", "{jr}preloadParams": "start"},
                {"id": "%s3" % id, "nodeset": "meta/timeEnd", "type": "xsd:dateTime", "{jr}preload": "timestamp", "{jr}preloadParams": "end"},
                {"id": "%s4" % id, "nodeset": "meta/username", "type": "xsd:string", "{jr}preload": "meta", "{jr}preloadParams": "UserName"},
                {"id": "%s5" % id, "nodeset": "meta/userID", "type": "xsd:string", "{jr}preload": "meta", "{jr}preloadParams": "UserID"},
                {"id": "%s6" % id, "nodeset": "meta/instanceID", "type": "xsd:string", "{jr}preload": "uid", "{jr}preloadParams": "general"},
            ]
            for bind in binds:
                bind = _make_elem('bind', bind)
                bind_parent.append(bind)
        add_meta()
        # apply any other transformations
        # necessary to make casexml work
        transformation()

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
        conflicting = self.model_node.find('{f}instance[@id="%s"]' % id)
        if not conflicting.exists():
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
            else:
                template = u"{path} = '{answer}'"
            return template.format(
                path=self.resolve_path(condition.question),
                answer=condition.answer
            )
        else:
            return 'false()'

    def create_casexml_2(self, form):
        from corehq.apps.app_manager.util import split_path

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
                case_id = session_var(form.session_var_for_action('open_case'))
                case_block.add_create_block(
                    relevance=self.action_relevance(open_case_action.condition),
                    case_name=open_case_action.name_path,
                    case_type=form.get_case_type(),
                    autoset_owner_id=autoset_owner_id_for_open_case(actions),
                    has_case_sharing=form.get_app().case_sharing,
                    case_id=case_id
                )
                if 'external_id' in actions['open_case'] and actions['open_case'].external_id:
                    extra_updates['external_id'] = actions['open_case'].external_id
            else:
                self.add_bind(
                    nodeset="case/@case_id",
                    calculate=SESSION_CASE_ID,
                )

            if 'update_case' in actions or extra_updates:
                self.add_case_updates(
                    case_block,
                    getattr(actions.get('update_case'), 'update', {}),
                    extra_updates=extra_updates)

            if 'close_case' in actions:
                case_block.add_close_block(self.action_relevance(actions['close_case'].condition))

            if 'case_preload' in actions:
                self.add_casedb()
                for nodeset, property in actions['case_preload'].preload.items():
                    # Skip usercase properties
                    if property.startswith(USERCASE_PREFIX):
                        continue
                    parent_path, property = split_path(property)
                    property_xpath = {
                        'name': 'case_name',
                        'owner_id': '@owner_id'
                    }.get(property, property)

                    id_xpath = get_case_parent_id_xpath(parent_path)
                    self.add_setvalue(
                        ref=nodeset,
                        value=id_xpath.case().property(property_xpath),
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
                    case_id = session_var(form.session_var_for_action('subcase', i))

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
                raise XFormException("You cannot use the Case Management UI if you already have a case block in your form.")
            else:
                case_parent.append(case_block.elem)
                if delegation_case_block is not None:
                    case_parent.append(delegation_case_block.elem)

        if not case_parent.exists():
            raise XFormException("Couldn't get the case XML from one of your forms. "
                             "A common reason for this is if you don't have the "
                             "xforms namespace defined in your form. Please verify "
                             'that the xmlns="http://www.w3.org/2002/xforms" '
                             "attribute exists in your form.")

    def create_casexml_2_advanced(self, form):
        from corehq.apps.app_manager.util import split_path

        def configure_visit_schedule_updates(update_block):
            update_block.append(make_case_elem(SCHEDULE_PHASE))
            last_visit_num = SCHEDULE_LAST_VISIT.format(form.schedule_form_id)
            last_visit_date = SCHEDULE_LAST_VISIT_DATE.format(form.schedule_form_id)
            update_block.append(make_case_elem(last_visit_num))

            self.add_setvalue(
                ref='case/update/{}'.format(SCHEDULE_PHASE),
                value=str(form.id + 1)
            )

            last_visit_prop_xpath = SESSION_CASE_ID.case().slash(last_visit_num)
            self.add_setvalue(
                ref='case/update/{}'.format(last_visit_num),
                value="if({0} = '', 1, int({0}) + 1)".format(last_visit_prop_xpath)
            )

            self.add_bind(
                nodeset='case/update/{}'.format(last_visit_date),
                type="xsd:dateTime",
                calculate=self.resolve_path("meta/timeEnd")
            )

        if not form.actions.get_all_actions():
            return

        case_tag = lambda a: "case_{0}".format(a.case_tag)

        def create_case_block(action, bind_case_id_xpath=None):
            tag = case_tag(action)
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

        last_real_action = next(
            (action for action in reversed(form.actions.load_update_cases) if not action.auto_select),
            None
        )

        module = form.get_module()
        has_schedule = module.has_schedule and form.schedule and form.schedule.anchor

        adjusted_datums = {}
        if module.root_module and module.root_module.module_type == 'basic':
            # for child modules the session variable for a case may have been
            # changed to match the parent module.
            from corehq.apps.app_manager.suite_xml import SuiteGenerator
            gen = SuiteGenerator(form.get_app())
            datums_meta, _ = gen.get_datum_meta_assertions_advanced(module, form)
            adjusted_datums = {
                getattr(meta['action'], 'id', None): meta['datum'].id
                for meta in datums_meta
                if meta['action']
            }

        for action in form.actions.get_load_update_actions():
            var_name = adjusted_datums.get(action.id, action.case_session_var)
            session_case_id = CaseIDXPath(session_var(var_name))
            if action.preload:
                self.add_casedb()
                for property, nodeset in action.preload.items():
                    if property.startswith(USERCASE_PREFIX):
                        # Ignore usercase properties
                        continue
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

                if has_schedule:
                    configure_visit_schedule_updates(update_case_block.update_block)

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
                name = case_tag(action)
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
                autoset_owner_id=('owner_id' not in action.case_properties),
                has_case_sharing=form.get_app().case_sharing,
                case_id=case_id
            )

            if action.case_properties:
                open_case_block.add_update_block(action.case_properties)

            if action.parent_tag:
                parent_meta = form.actions.actions_meta_by_tag.get(action.parent_tag)
                reference_id = action.parent_reference_id or 'parent'
                if parent_meta['type'] == 'load':
                    ref = CaseIDXPath(session_var(parent_meta['action'].case_session_var))
                else:
                    path, _ = get_action_path(parent_meta['action'], create_subcase_node=False)
                    ref = self.resolve_path("%scase/@case_id" % path)

                open_case_block.add_index_ref(
                    reference_id,
                    parent_meta['action'].case_type,
                    ref,
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

    def create_casexml_1(self, form):
        from xml_utils import XMLTag as __

        actions = form.active_actions()
        # a list of functions to be applied to the file as a whole after it has been pieced together
        additional_transformations = []


        if form.requires == 'none' and 'open_case' not in actions and actions:
            raise CaseError("To perform case actions you must either open a case or require a case to begin with")

        binds = []
        if form.requires == 'none' and not actions:
            casexml_text = ""
        else:
            def add_bind(d):
                binds.append(_make_elem('bind', d))

            casexml = __('case')[
                      __("case_id"),
                      __("date_modified")
            ]

            add_bind({"nodeset":"case/date_modified", "type":"dateTime", "{jr}preload":"timestamp", "{jr}preloadParams":"end"})

            if 'open_case' in actions:
                casexml[
                __('create')[
                __("case_type_id")[form.get_case_type()],
                __("case_name"),
                __("user_id"),
                __("external_id"),
                ]
                ]
                r = self.action_relevance(actions['open_case'].condition)
                if r != "true()":
                    add_bind({
                        "nodeset":"case",
                        'relevant': r
                    })
                add_bind({
                    "nodeset":"case/create",
                    'relevant': r
                })
                add_bind({
                    "nodeset":"case/case_id",
                    "{jr}preload":"uid",
                    "{jr}preloadParams":"general",
                    })
                add_bind({
                    'nodeset':"case/create/user_id",
                    'type':"xsd:string",
                    '{jr}preload': "meta",
                    '{jr}preloadParams': "UserID",
                    })
                add_bind({
                    "nodeset":"case/create/case_name",
                    "calculate":self.resolve_path(actions['open_case'].name_path),
                    })
                if 'external_id' in actions['open_case'] and actions['open_case'].external_id:
                    add_bind({
                        "nodeset":"case/create/external_id",
                        "calculate": self.resolve_path(actions['open_case'].external_id),
                        })
                else:
                    add_bind({
                        "nodeset":"case/create/external_id",
                        "calculate": self.resolve_path("case/case_id"),
                        })
                def require_case_name_source():
                    "make sure that the question that provides the case_name is required"
                    name_path = actions['open_case'].name_path
                    if not name_path:
                        raise CaseError("Please set 'Name according to question'. "
                                        "This will give each case a 'name' attribute")
                    name_bind = self.get_bind(name_path)

                    if name_bind.exists():
                        name_bind.attrib['required'] = "true()"
                    else:
                        self.model_node.xml.append(_make_elem('bind', {
                            "nodeset": name_path,
                            "required": "true()"
                        }))
                additional_transformations.append(require_case_name_source)

            else:
                add_bind({"nodeset":"case/case_id", "{jr}preload":"case", "{jr}preloadParams":"case-id"})
            if 'update_case' in actions:
                # no condition

                update_mapping = {}
                for key, value in actions['update_case'].update.items():
                    if key == 'name':
                        key = 'case_name'
                    update_mapping[key] = value

                casexml[
                __('update')[
                (__(key) for key in update_mapping.keys())
                ]
                ]
                for key, path in update_mapping.items():
                    add_bind({"nodeset":"case/update/%s" % key, "calculate": self.resolve_path(path), "relevant": "count(%s) > 0" % path})
            if 'close_case' in actions:
                casexml[
                __('close')
                ]
                r = self.action_relevance(actions['close_case'].condition)
                add_bind({
                    "nodeset": "case/close",
                    "relevant": r,
                    })

            if 'open_referral' in actions or 'update_referral' in actions or 'close_referral' in actions:
                referral = __('referral')[
                           __('referral_id'),
                ]
                if 'open_referral' in actions or 'update_referral' in actions:
                    referral[__('followup_date')]
                casexml[referral]

                if 'open_referral' in actions:
                    # no condition
                    referral[
                    __("open")[
                    __("referral_types")
                    ]
                    ]
                    add_bind({
                        "nodeset":"case/referral",
                        "relevant":"count-selected(%s) > 0" % self.resolve_path(actions['open_referral'].name_path)
                    })
                    add_bind({
                        "nodeset":"case/referral/referral_id",
                        "{jr}preload":"uid",
                        "{jr}preloadParams":"general",
                        })
                    add_bind({
                        "nodeset":"case/referral/followup_date",
                        "type":"xsd:date",
                        # trust get_followup_date to return xpath with absolute paths
                        "calculate": actions['open_referral'].get_followup_date()
                    })
                    add_bind({
                        "nodeset":"case/referral/open/referral_types",
                        "calculate": self.resolve_path(actions['open_referral'].name_path),
                        })
                if 'update_referral' in actions or 'close_referral' in actions:
                    # no condition
                    referral_update = __("update")[
                                      __("referral_type")
                    ]
                    referral[referral_update]

                    add_bind({
                        "nodeset":"case/referral/referral_id",
                        "{jr}preload":"patient_referral",
                        "{jr}preloadParams":"id"
                    })
                    add_bind({
                        "nodeset":"case/referral/update/referral_type",
                        "{jr}preload":"patient_referral",
                        "{jr}preloadParams":"type"
                    })

                if 'update_referral' in actions:
                    # no condition
                    if actions['update_referral'].followup_date:
                        add_bind({
                            "nodeset": "case/referral/followup_date",
                            "type":"xsd:date",
                            # trust get_followup_date to return xpath with absolute paths
                            "calculate": actions['update_referral'].get_followup_date(),
                            })
                if 'close_referral' in actions:
                    referral_update[__("date_closed")]
                    r = self.action_relevance(actions['close_referral'].condition)
                    add_bind({
                        "nodeset":"case/referral/update/date_closed",
                        "relevant": r,
                        "{jr}preload":"timestamp",
                        "{jr}preloadParams":"end"
                    })

            if 'case_preload' in actions:
                for nodeset, property in actions['case_preload'].preload.items():
                    add_bind({
                        "nodeset": nodeset,
                        "{jr}preload":"case",
                        "{jr}preloadParams": property
                    })
            if 'referral_preload' in actions:
                for nodeset, property in actions['referral_preload'].preload.items():
                    add_bind({
                        "nodeset": nodeset,
                        "{jr}preload":"referral",
                        "{jr}preloadParams": property
                    })
            casexml_text = casexml.render()
        def transformation():
            for trans in additional_transformations:
                trans()
        return casexml_text, binds, transformation

    def add_user_registration(self, username_path='username', password_path='password', data_paths=None):
        data_paths = data_paths or {}

        if self.data_node.find("{reg}registration").exists():
            return

        # registration
        registration = ET.Element("{reg}registration".format(**namespaces), nsmap={None: namespaces['reg'][1:-1]})
        ET.SubElement(registration, "{reg}username".format(**namespaces))
        ET.SubElement(registration, "{reg}password".format(**namespaces))
        ET.SubElement(registration, "{reg}uuid".format(**namespaces))
        ET.SubElement(registration, "{reg}date".format(**namespaces))
        ET.SubElement(registration, "{reg}registering_phone_id".format(**namespaces))
        user_data = ET.SubElement(registration, "{reg}user_data".format(**namespaces))
        for key in data_paths:
            # $('<reg:' + key + '/>').attr('key', key).appendTo(user_data)
            ET.SubElement(user_data, ("{reg}%s" % key).format(**namespaces)).set('key', key)
        self.data_node.append(registration)

        # hq_tmp
        HQ_TMP = 'hq_tmp'
        hq_tmp = ET.Element(("{x}%s" % HQ_TMP).format(**namespaces))
        ET.SubElement(hq_tmp, "{x}loadedguid".format(**namespaces))
        ET.SubElement(hq_tmp, "{x}freshguid".format(**namespaces))
        self.data_node.append(hq_tmp)

        # binds: username, password
        for key, path in [('username', username_path), ('password', password_path)]:
            self.model_node.append(_make_elem('{f}bind', {
                'nodeset': self.resolve_path('registration/%s' % key),
                'calculate': self.resolve_path(path)
            }))

            # add required="true()" to binds of required elements
            bind = self.get_bind(self.resolve_path(path))
            if not bind.exists():
                bind = _make_elem('{f}bind', {
                    'nodeset': self.resolve_path(path),
                    })
                self.model_node.append(bind)
            bind.set('required', "true()")

        # binds: hq_tmp/loadedguid, hq_tmp/freshguid, registration/date, registration/registering_phone_id

        for path, type, preload, preload_params in [
            ('registration/date', 'xsd:dateTime', 'timestamp', 'start'),
            ('registration/registering_phone_id', 'xsd:string', 'property', 'DeviceID'),
            ('%s/loadedguid' % HQ_TMP, 'xsd:string', 'user', 'uuid'),
            ('%s/freshguid' % HQ_TMP, 'xsd:string', 'uid', 'general'),
        ]:
            self.model_node.append(_make_elem('{f}bind', {
                'nodeset': self.resolve_path(path),
                'type': type,
                '{jr}preload': preload,
                '{jr}preloadParams': preload_params,
            }))


        # bind: registration/uuid
        self.model_node.append(_make_elem('{f}bind', {
            'nodeset': self.resolve_path('registration/uuid'),
            'type': 'xsd:string',
            'calculate': "if({loadedguid}='', {freshguid}, {loadedguid})".format(
                loadedguid=self.resolve_path('%s/loadedguid' % HQ_TMP),
                freshguid=self.resolve_path('%s/freshguid' % HQ_TMP),
            )
        }))

        # user_data binds
        for key, path in data_paths.items():
            self.model_node.append(_make_elem('{f}bind', {
                'nodeset': self.resolve_path('registration/user_data/%s' % key),
                'calculate': self.resolve_path(path),
            }))

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
        'type': 'xsd:datetime',
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
