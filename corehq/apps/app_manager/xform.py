from casexml.apps.case.xml import V2_NAMESPACE
from corehq.apps.app_manager.const import APP_V1
from lxml import etree as ET
import formtranslate.api


def parse_xml(string):
    # Work around: ValueError: Unicode strings with encoding
    # declaration are not supported.
    if isinstance(string, unicode):
        string = string.encode("utf-8")
    try:
        return ET.fromstring(string, parser=ET.XMLParser(encoding="utf-8", remove_comments=True))
    except ET.ParseError, e:
        raise XFormError("Error parsing XML" + (": %s" % e if e.message else ""))

class XFormError(Exception):
    pass

class CaseError(XFormError):
    pass

class XFormValidationError(XFormError):
    pass

namespaces = dict(
    jr = "{http://openrosa.org/javarosa}",
    xsd = "{http://www.w3.org/2001/XMLSchema}",
    h='{http://www.w3.org/1999/xhtml}',
    f='{http://www.w3.org/2002/xforms}',
    ev="{http://www.w3.org/2001/xml-events}",
    orx="{http://openrosa.org/jr/xforms}",
    reg="{http://openrosa.org/user/registration}",
    cx2="{%s}" % V2_NAMESPACE,
    cc="{http://commcarehq.org/xforms}",
)

def _make_elem(tag, attr=None):
    attr = attr or {}
    return ET.Element(tag.format(**namespaces), dict([(key.format(**namespaces), val) for key,val in attr.items()]))

class XPath(unicode):
    def slash(self, xpath):
        if self:
            return XPath(u'%s/%s' % (self, xpath))
        else:
            return XPath(xpath)

class CaseIDXPath(XPath):

    def case(self):
        return CaseXPath(u"instance('casedb')/casedb/case[@case_id=%s]" % self)

class CaseXPath(XPath):

    def index_id(self, name):
        return CaseIDXPath(self.slash(u'index').slash(name))

    def parent_id(self):
        return self.index_id('parent')

    def property(self, property):
        return self.slash(property)

SESSION_CASE_ID = CaseIDXPath(u"instance('commcaresession')/session/data/case_id")


class WrappedNode(object):
    def __init__(self, xml, namespaces=namespaces):
        if isinstance(xml, basestring):
            self.xml = parse_xml(xml) if xml else None
        else:
            self.xml = xml
        self.namespaces=namespaces

    def __getattr__(self, name):
        if name in ('find', 'findall', 'findtext'):
            wrap = {
                'find': WrappedNode,
                'findall': lambda list: map(WrappedNode, list),
                'findtext': lambda text: text
            }[name]
            none = {
                'find': lambda: WrappedNode(None),
                'findall': list,
                'findtext': lambda: None
            }[name]
            def _fn(xpath, *args, **kwargs):
                if self.xml is not None:
                    return wrap(getattr(self.xml, name)(xpath.format(**self.namespaces), *args, **kwargs))
                else:
                    return none()
            return _fn
        else:
            return getattr(self.xml, name)

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
                raise XFormError(message)
            else:
                return n
        return _fn
    return decorator

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

    def validate(self, version='1.0'):
        r = formtranslate.api.validate(ET.tostring(self.xml), version=version)
        if not r['success']:
            raise XFormValidationError(r["errstring"])
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

    def media_references(self, form):
        try:
            nodes = self.itext_node.findall('{f}translation/{f}text/{f}value[@form="%s"]' % form)
            return [n.text for n in nodes]
        except XFormError:
            return []
    @property
    def image_references(self):
        return self.media_references(form="image")

    @property
    def audio_references(self):
        return self.media_references(form="audio")

    def rename_language(self, old_code, new_code):
        trans_node = self.itext_node.find('{f}translation[@lang="%s"]' % old_code)
        duplicate_node = self.itext_node.find('{f}translation[@lang="%s"]' % new_code)
        if not trans_node.exists():
            raise XFormError("There's no language called '%s'" % old_code)
        if duplicate_node.exists():
            raise XFormError("There's already a language called '%s'" % new_code)
        trans_node.attrib['lang'] = new_code

    def exclude_languages(self, whitelist):
        try:
            translations = self.itext_node.findall('{f}translation')
        except XFormError:
            # if there's no itext then they must be using labels
            return

        for trans_node in translations:
            if trans_node.attrib.get('lang') not in whitelist:
                self.itext_node.remove(trans_node.xml)

    def localize(self, id, lang=None, form=None):
        pre = 'jr:itext('
        post = ')'

        if id.startswith(pre) and post[-len(post):] == post:
            id = id[len(pre):-len(post)]
        if id[0] == id[-1] and id[0] in ('"', "'"):
            id = id[1:-1]

        if lang is None:
            trans_node = self.itext_node.find('{f}translation')
        else:
            trans_node = self.itext_node.find('{f}translation[@lang="%s"]' % lang)
            if not trans_node.exists():
                return None
        text_node = trans_node.find('{f}text[@id="%s"]' % id)
        if not text_node.exists():
            return None

        search_tag = '{f}value'
        if form:
            search_tag += '[@form="%s"]' % form
        value_node = text_node.find(search_tag)

        _safe_strip = lambda x: x if isinstance(x, unicode) else str.strip(x)
        if value_node:
            text = " ____ ".join([t for t in map(_safe_strip, value_node.itertext()) if t])
        else:
            raise XFormError('<translation lang="%s"><text id="%s"> node has no <value>' % (
                trans_node.attrib.get('lang'), id
            ))


        return text

    def get_label_text(self, prompt, langs, form=None):
        label_node = prompt.find('{f}label')
        label = ""
        if label_node.exists():
            if 'ref' in label_node.attrib:
                for lang in langs + [None]:
                    label = self.localize(label_node.attrib['ref'], lang, form)
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

    def get_languages(self):
        if not self.exists():
            return []
        try:
            itext = self.itext_node
        except:
            return []
        langs = []
        for translation in itext.findall('{f}translation'):
            langs.append(translation.attrib['lang'])
        return langs


    def get_questions(self, langs):
        """
        parses out the questions from the xform, into the format:
        [{"label": label, "tag": tag, "value": value}, ...]

        if the xform is bad, it will raise an XFormError

        """

        if not self.exists():
            return []

        def get_path(prompt):
            # TODO: add safety tests so that when something fails it fails with a good error
            path = None
            if 'ref' in prompt.attrib:
                path = prompt.attrib['ref']
            elif 'bind' in prompt.attrib:
                bind_id = prompt.attrib['bind']
                bind = self.model_node.find('{f}bind[@id="%s"]' % bind_id)
                path = bind.attrib['nodeset']
            elif prompt.tag_name == "group":
                path = ""
            elif prompt.tag_name == "repeat":
                path = prompt.attrib['nodeset']
            else:
                raise XFormError("Node <%s> has no 'ref' or 'bind'" % prompt.tag_name)
            return path

        questions = []
        excluded_paths = set()

        def build_questions(group, path_context="", exclude=False):
            for prompt in group.findall('*'):
                if prompt.tag_xmlns == namespaces['f'][1:-1] and prompt.tag_name != "label":
                    path = self.resolve_path(get_path(prompt), path_context)
                    excluded_paths.add(path)
                    if prompt.tag_name == "group":
                        build_questions(prompt, path_context=path)
                    elif prompt.tag_name == "repeat":
                        build_questions(prompt, path_context=path, exclude=True)
                    elif prompt.tag_name not in ("trigger", "label"):
                        if not exclude:
                            question = {
                                "label": self.get_label_text(prompt, langs),
                                "tag": prompt.tag_name,
                                "value": path
                            }

                            if question['tag'] == "select1":
                                options = []
                                for item in prompt.findall('{f}item'):
                                    translation = self.get_label_text(item, langs)
                                    try:
                                        value = item.findtext('{f}value').strip()
                                    except AttributeError:
                                        raise XFormError("<item> (%r) has no <value>" % translation)
                                    options.append({
                                        'label': translation,
                                        'value': value
                                    })
                                question.update({'options': options})
                            questions.append(question)
        build_questions(self.find('{h}body'))


        def build_non_question_paths(parent, path_context=""):
            for child in parent.findall('*'):
                path = self.resolve_path(child.tag_name, path_context)
                build_non_question_paths(child, path_context=path)
            if not parent.findall('*'):
                path = path_context
                if path not in excluded_paths:
                    questions.append({
                        "label": path,
                        "tag": "hidden",
                        "value": path
                    })
        build_non_question_paths(self.data_node)
        return questions

    def add_case_and_meta(self, form):
        if form.get_app().application_version == APP_V1:
            self.add_case_and_meta_1(form)
        else:
            self.add_case_and_meta_2(form)

    def already_has_meta(self):
        meta_blocks = set()
        for meta_xpath in ('{orx}meta', '{x}meta', '{orx}Meta', '{x}Meta'):
            meta = self.data_node.find(meta_xpath)
            if meta.exists():
                meta_blocks.add(meta)

        return meta_blocks

    def add_case_and_meta_2(self, form):
        case = self.case_node

        case_parent = self.data_node

        self.create_casexml_2(form)

        # Test all of the possibilities so that we don't end up with two "meta" blocks
        for meta in self.already_has_meta():
            case_parent.remove(meta.xml)

        def add_meta():
            orx = namespaces['orx'][1:-1]
            nsmap = {None: orx, 'cc': namespaces['cc'][1:-1]}

            meta = ET.Element("{orx}meta".format(**namespaces), nsmap=nsmap)
            for tag in (
                '{orx}deviceID',
                '{orx}timeStart',
                '{orx}timeEnd',
                '{orx}username',
                '{orx}userID',
                '{orx}instanceID',
                '{cc}appVersion',
            ):
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
        add_meta()

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
            raise XFormError("Couldn't get the case XML from one of your forms. "
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

    def set_default_language(self, lang):
        try:
            itext_node = self.itext_node
        except XFormError:
            return
        else:
            for translation in itext_node.findall('{f}translation'):
                if translation.attrib.get('lang') == lang:
                    translation.attrib['default'] = ""
                else:
                    translation.attrib.pop('default', None)

    def set_version(self, version):
        """set the form's version attribute"""
        self.data_node.set('version', "%s" % version)


    def add_bind(self, **d):
        if d.get('relevant') == 'true()':
            del d['relevant']
        d['nodeset'] = self.resolve_path(d['nodeset'])
        if len(d) > 1:
            bind = _make_elem('bind', d)
            conflicting = self.model_node.find('{f}bind[@nodeset="%s"]' % bind.attrib['nodeset'])
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

    def create_casexml_2(self, form):

        actions = form.active_actions()

        if form.requires == 'none' and 'open_case' not in actions and 'update_case' in actions:
            raise CaseError("To update a case you must either open a case or require a case to begin with")

        def make_case_elem(tag, attr=None):
            return _make_elem('{cx2}%s' % tag, attr)
        def make_case_block(path=''):
            case_block = ET.Element('{cx2}case'.format(**namespaces), {
                'case_id': '',
                'date_modified': '',
                'user_id': '',
                }, nsmap={
                None: namespaces['cx2'][1:-1]
            })

            self.add_bind(
                nodeset="%scase/@date_modified" % path,
                type="dateTime",
                calculate=self.resolve_path("meta/timeEnd")
            )
            self.add_bind(
                nodeset="%scase/@user_id" % path,
                calculate=self.resolve_path("meta/userID"),
            )
            return case_block

        def relevance(action):
            if action.condition.type == 'always':
                return 'true()'
            elif action.condition.type == 'if':
                return "%s = '%s'" % (self.resolve_path(action.condition.question), action.condition.answer)
            else:
                return 'false()'

        def add_create_block(case_block, action, case_name, case_type, path=''):
            create_block = make_case_elem('create')
            case_block.append(create_block)
            case_type_node = make_case_elem('case_type')
            case_type_node.text = case_type
            create_block.extend([
                make_case_elem('case_name'),
                make_case_elem('owner_id'),
                case_type_node,
                ])
            self.add_bind(
                nodeset='%scase' % path,
                relevant=relevance(action),
            )
            self.add_setvalue(
                ref="%scase/@case_id" % path,
                value="uuid()",
            )
            self.add_bind(
                nodeset="%scase/create/case_name" % path,
                calculate=self.resolve_path(case_name),
            )

            if form.get_app().case_sharing:
                self.add_instance('groups', src='jr://fixture/user-groups')
                self.add_setvalue(
                    ref="%scase/create/owner_id" % path,
                    value="instance('groups')/groups/group/@id"
                )
            else:
                self.add_bind(
                    nodeset="%scase/create/owner_id" % path,
                    calculate=self.resolve_path("meta/userID"),
                )

            if not case_name:
                raise CaseError("Please set 'Name according to question'. "
                                "This will give each case a 'name' attribute")
            self.add_bind(
                nodeset=case_name,
                required="true()",
            )
        def add_update_block(case_block, updates, path='', extra_updates=None):
            update_block = make_case_elem('update')
            case_block.append(update_block)
            update_mapping = {}

            if updates:
                for key, value in updates.items():
                    if key == 'name':
                        key = 'case_name'
                    update_mapping[key] = value

            if extra_updates:
                update_mapping.update(extra_updates)

            for key in update_mapping.keys():
                update_block.append(make_case_elem(key))

            for key, q_path in update_mapping.items():
                self.add_bind(
                    nodeset="%scase/update/%s" % (path, key),
                    calculate=self.resolve_path(q_path),
                    relevant=("count(%s) > 0" % self.resolve_path(q_path))
                )
        def add_close_block(case_block, action=None, path=''):
            case_block.append(make_case_elem('close'))
            self.add_bind(
                nodeset="%scase/close" % path,
                relevant=relevance(action) if action else 'true()',
            )
        delegation_case_block = None
        if not actions or (form.requires == 'none' and 'open_case' not in actions):
            case_block = None
        else:
            extra_updates = {}
            needs_casedb_instance = False

            case_block = make_case_block()
            if form.requires != 'none':
                def make_delegation_stub_case_block():
                    path = 'cc_delegation_stub/'
                    DELEGATION_ID = 'delegation_id'
                    outer_block = _make_elem('{x}cc_delegation_stub', {DELEGATION_ID: ''})
                    delegation_case_block = make_case_block(path)
                    add_close_block(delegation_case_block)
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
                    outer_block.append(delegation_case_block)
                    return outer_block


                if form.get_module().task_list.show:
                    delegation_case_block = make_delegation_stub_case_block()

            if 'open_case' in actions:
                open_case_action = actions['open_case']
                add_create_block(case_block, open_case_action, case_name=open_case_action.name_path, case_type=form.get_case_type())
                if 'external_id' in actions['open_case'] and actions['open_case'].external_id:
                    extra_updates['external_id'] = actions['open_case'].external_id
            else:
                self.add_bind(
                    nodeset="case/@case_id",
                    calculate=SESSION_CASE_ID,
                )

            if 'update_case' in actions or extra_updates:
                add_update_block(case_block, getattr(actions.get('update_case'), 'update', {}), extra_updates=extra_updates)

            if 'close_case' in actions:
                add_close_block(case_block, actions['close_case'])

            if 'case_preload' in actions:
                needs_casedb_instance = True
                for nodeset, property in actions['case_preload'].preload.items():
                    property_xpath = {
                        'name': 'case_name',
                        'owner_id': '@owner_id'
                    }.get(property, property)
                    self.add_setvalue(
                        ref=nodeset,
                        value=SESSION_CASE_ID.case().property(property_xpath),
                    )
            if needs_casedb_instance:
                self.add_instance('casedb', src='jr://instance/casedb')

        if 'subcases' in actions:
            for i, subcase in enumerate(actions['subcases']):
                name = 'subcase_%s' % i
                path = '%s/' % name
                subcase_node = _make_elem('{x}%s' % name)
                subcase_block = make_case_block(path)

                add_create_block(subcase_block, subcase,
                    case_name=subcase.case_name,
                    case_type=subcase.case_type,
                    path=path
                )

                add_update_block(subcase_block, subcase.case_properties, path=path)

                if case_block is not None and subcase.case_type != form.get_case_type():
                    index_node = make_case_elem('index')
                    parent_index = make_case_elem('parent', {'case_type': form.get_case_type()})
                    self.add_bind(
                        nodeset='%s/case/index/parent' % name,
                        calculate=self.resolve_path("case/@case_id"),
                    )
                    index_node.append(parent_index)
                    subcase_block.append(index_node)

                subcase_node.append(subcase_block)
                self.data_node.append(subcase_node)


        # always needs session instance for meta
        self.add_instance('commcaresession', src='jr://instance/session')


        case = self.case_node
        case_parent = self.data_node

        if case_block is not None:
            if case.exists():
                raise XFormError("You cannot use the Case Management UI if you already have a case block in your form.")
            else:
                case_parent.append(case_block)
                if delegation_case_block is not None:
                    case_parent.append(delegation_case_block)

        if not case_parent.exists():
            raise XFormError("Couldn't get the case XML from one of your forms. "
                             "A common reason for this is if you don't have the "
                             "xforms namespace defined in your form. Please verify "
                             'that the xmlns="http://www.w3.org/2002/xforms" '
                             "attribute exists in your form.")

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


            def relevance(action):
                if action.condition.type == 'always':
                    return 'true()'
                elif action.condition.type == 'if':
                    return "%s = '%s'" % (self.resolve_path(action.condition.question), action.condition.answer)
                else:
                    return 'false()'
            if 'open_case' in actions:
                casexml[
                __('create')[
                __("case_type_id")[form.get_case_type()],
                __("case_name"),
                __("user_id"),
                __("external_id"),
                ]
                ]
                r = relevance(actions['open_case'])
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
                    name_bind = self.model_node.find('{f}bind[@nodeset="%s"]' % name_path)

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
                r = relevance(actions['close_case'])
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
                    r = relevance(actions['close_referral'])
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
            bind = self.model_node.find('{f}bind[@nodeset="%s"]' % self.resolve_path(path))
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
