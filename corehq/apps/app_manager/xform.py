from lxml import etree as ET


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

namespaces = dict(
    jr = "{http://openrosa.org/javarosa}",
    xsd = "{http://www.w3.org/2001/XMLSchema}",
    h='{http://www.w3.org/1999/xhtml}',
    f='{http://www.w3.org/2002/xforms}',
    ev="{http://www.w3.org/2001/xml-events}",
    orx="{http://openrosa.org/jr/xforms}",
)

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
            def _fn(xpath, *args, **kwargs):
                return wrap(getattr(self.xml, name)(xpath.format(**self.namespaces), *args, **kwargs))
            return _fn
        else:
            return getattr(self.xml, name)

    @property
    def tag_xmlns(self):
        return self.tag.split('}')[0][1:]

    @property
    def tag_name(self):
        return self.tag.split('}')[1]


class XForm(WrappedNode):
    def __init__(self, *args, **kwargs):
        super(XForm, self).__init__(*args, **kwargs)
        xmlns = self.data_node.tag_xmlns
        self.namespaces.update(x=xmlns)

    @property
    def model_node(self):
        return self.find('{h}head/{f}model')

    @property
    def instance_node(self):
        return self.find('{h}head/{f}model')

    @property
    def data_node(self):
        return self.model_node.find('{f}instance/*')

    @property
    def itext_node(self):
        return self.model_node.find('{f}itext')

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
            if trans_node is None:
                return None
        text_node = trans_node.find('{f}text[@id="%s"]' % id)
        if form:
            text = text_node.findtext('{f}value[@form="%s"]' % form).strip()
        else:
            text = text_node.findtext('{f}value').strip()

        return text

    def get_label_text(self, prompt, langs, form=None):
        label_node = prompt.find('{f}label')
        label = ""
        if label_node is not None:
            if 'ref' in label_node.attrib:
                for lang in langs + [None]:
                    label = self.localize(label_node.attrib['ref'], lang, form)
                    if label is not None:
                        break
            else:
                label = label_node.text.strip()

        return label
    
    def get_questions(self, langs):
        """
        parses out the questions from the xform, into the format:
        [{"label": label, "tag": tag, "value": value}, ...]

        if the xform is bad, it will raise an XFormError

        """

        if self.xml is None:
            return []

        def get_path(prompt):
            try:
                path = prompt.attrib['ref']
            except:
                bind_id = prompt.attrib['bind']
                bind = self.model_node.find('{f}bind[@id="%s"]' % bind_id)
                path = bind.attrib['nodeset']
            return path
        questions = []

        def build_questions(group, context=""):
            for prompt in group.findall('*'):
                if prompt.tag == namespaces['f'] + "group":
                    build_questions(prompt)
                elif prompt.tag == namespaces['f'] + "trigger":
                    continue
                else:
                    question = {
                        "label": self.get_label_text(prompt, langs),
                        "tag": prompt.tag_name,
                        "value": get_path(prompt),
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
        return questions