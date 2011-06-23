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
        raise XFormError("Problem parsing an XForm. The parsing error is: %s" % (e if e.message else "unknown"))

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
)

def _make_elem(tag, attr):
    return ET.Element(tag, dict([(key.format(**namespaces), val) for key,val in attr.items()]))

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
            self.validate()
            #print "Incoming XForm %s OK" % xmlns

    def validate(self):
        r = formtranslate.api.validate(ET.tostring(self.xml))
        if not r['success']:
            raise XFormValidationError(r["errstring"])

    def render(self, validate=False):
        if validate:
            self.validate()
            #print "Outgoing XForm %s OK" % self.data_node.tag_xmlns
        return ET.tostring(self.xml)
    
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
        return self.data_node.find('{x}case')

    def rename_language(self, old_code, new_code):
        trans_node = self.itext_node.find('{f}translation[@lang="%s"]' % old_code)
        if not trans_node.exists():
            raise XFormError("There's no language called '%s'" % old_code)
        trans_node.attrib['lang'] = new_code

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
        if form:
            text = text_node.findtext('{f}value[@form="%s"]' % form).strip()
        else:
            text = text_node.findtext('{f}value').strip()

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
            else:
                label = label_node.text.strip()

        return label

    def resolve_path(self, path, path_context=""):
        if path == "":
            return path_context
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
                                    options.append({
                                        'label': translation,
                                        'value': item.findtext('{f}value').strip()
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
        case = self.case_node

        case_parent = self.data_node
        bind_parent = self.model_node

        casexml, binds, transformation = self.create_casexml(form)
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
                bind_parent.append(bind)

        if not case_parent.exists():
            raise XFormError("Couldn't get the case XML from one of your forms. "
                             "A common reason for this is if you don't have the "
                             "xforms namespace defined in your form. Please verify "
                             'that the xmlns="http://www.w3.org/2002/xforms" '
                             "attribute exists in your form.")


        # Test all of the possibilities so that we don't end up with two "meta" blocks
        if  not case_parent.find('{orx}meta').exists() and \
            not case_parent.find('{x}meta').exists() and \
            not case_parent.find('{orx}Meta').exists() and \
            not case_parent.find('{x}Meta').exists():
            orx = namespaces['orx'][1:-1]
            nsmap = {"orx": orx}
            meta = ET.Element("{orx}meta".format(**namespaces), nsmap=nsmap)
            for tag in ('deviceID','timeStart', 'timeEnd','username','userID','uid'):
                meta.append(ET.Element(("{orx}%s"%tag).format(**namespaces), nsmap=nsmap))
            case_parent.append(meta)
            id = form.get_unique_id() + "meta"
            binds = [
                {"id": "%s1" % id, "nodeset": "meta/deviceID", "type": "xsd:string", "{jr}preload": "property", "{jr}preloadParams": "DeviceID"},
                {"id": "%s2" % id, "nodeset": "meta/timeStart", "type": "xsd:dateTime", "{jr}preload": "timestamp", "{jr}preloadParams": "start"},
                {"id": "%s3" % id, "nodeset": "meta/timeEnd", "type": "xsd:dateTime", "{jr}preload": "timestamp", "{jr}preloadParams": "end"},
                {"id": "%s4" % id, "nodeset": "meta/username", "type": "xsd:string", "{jr}preload": "meta", "{jr}preloadParams": "UserName"},
                {"id": "%s5" % id, "nodeset": "meta/userID", "type": "xsd:string", "{jr}preload": "meta", "{jr}preloadParams": "UserID"},
                {"id": "%s6" % id, "nodeset": "meta/uid", "type": "xsd:string", "{jr}preload": "uid", "{jr}preloadParams": "general"},
            ]
            for bind in binds:
                bind = _make_elem('bind', bind)
                bind_parent.append(bind)

        # apply any other transformations
        # necessary to make casexml work
        transformation()

    def create_casexml(self, form):
        from xml_utils import XMLTag as __

        actions = form.active_actions()
        # a list of functions to be applied to the file as a whole after it has been pieced together
        additional_transformations = []

        if not actions:
            casexml_text, binds = "", []
        else:
            binds = []
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
                    return "%s = '%s'" % (action.condition.question, action.condition.answer)
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
                        'relevance': r
                    })
                add_bind({
                    "nodeset":"case/create",
                    'relevance': r
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
                    "calculate":actions['open_case'].name_path,
                })
                if 'external_id' in actions['open_case'] and actions['open_case'].external_id:
                    add_bind({
                        "nodeset":"case/create/external_id",
                        "calculate":actions['open_case'].external_id,
                    })
                else:
                    add_bind({
                        "nodeset":"case/create/external_id",
                        "calculate":"case/create/case_id",
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
                casexml[
                    __('update')[
                        (__(key) for key in actions['update_case'].update.keys())
                    ]
                ]
                for key, path in actions['update_case'].update.items():
                    add_bind({"nodeset":"case/update/%s" % key, "calculate": path, "relevant": "count(%s) > 0" % path})
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
                        "relevant":"count-selected(%s) > 0" % actions['open_referral'].name_path
                    })
                    add_bind({
                        "nodeset":"case/referral/referral_id",
                        "{jr}preload":"uid",
                        "{jr}preloadParams":"general",
                    })
                    add_bind({
                        "nodeset":"case/referral/followup_date",
                        "type":"date",
                        "calculate": actions['open_referral'].get_followup_date()
                    })
                    add_bind({
                        "nodeset":"case/referral/open/referral_types",
                        "calculate": actions['open_referral'].name_path,
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
                            "calculate": actions['update_referral'].get_followup_date()
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
            casexml_text = casexml.render()
        def transformation():
            for trans in additional_transformations:
                trans()
        return casexml_text, binds, transformation