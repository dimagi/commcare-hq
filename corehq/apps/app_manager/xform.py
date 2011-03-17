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

class XForm(object):

    def __init__(self, xml):
        self.xml = parse_xml(xml) if xml else None


    def itext(self, id, lang=None, form=None):
        pre = 'jr:itext('
        post = ')'

        if id.startswith(pre) and post[-len(post):] == post:
            id = id[len(pre):-len(post)]
        if id[0] == id[-1] and id[0] in ('"', "'"):
            id = id[1:-1]

        if lang is None:
            x = self.xml.find('.//{f}translation'.format(**namespaces))
        else:
            x = self.xml.find('.//{f}translation[@lang="%s"]'.format(**namespaces) % lang)
            if x is None:
                return None
        x = x.find('{f}text[@id="%s"]'.format(**namespaces) % id)
        if form:
            x = x.findtext('{f}value[@form="%s"]'.format(**namespaces) % form).strip()
        else:
            x = x.findtext('{f}value'.format(**namespaces)).strip()

        return x

    def get_label_text(self, prompt, langs, form=None):
        label_node = prompt.find('{f}label'.format(**namespaces))
        label = ""
        if label_node is not None:
            if 'ref' in label_node.attrib:
                for lang in langs + [None]:
                    label = self.itext(label_node.attrib['ref'], lang, form)
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
                ref = prompt.attrib['ref']
            except KeyError:
                bind_id = prompt.attrib['bind']
                bind = self.xml.find('.//{f}bind[@id="%s"]'.format(**namespaces) % bind_id)
                ref = bind.attrib['nodeset']
            return ref
        questions = []

        def build_questions(group):
            for prompt in group.findall('*'):
                if prompt.tag == namespaces['f'] + "group":
                    build_questions(prompt)
                elif prompt.tag == namespaces['f'] + "trigger":
                    continue
                else:
                    question = {
                        "label": self.get_label_text(prompt, langs),
                        "tag": prompt.tag.split('}')[-1],
                        "value": get_path(prompt),
                    }

                    if question['tag'] == "select1":
                        options = []
                        for item in prompt.findall('{f}item'.format(**namespaces)):
                            translation = self.get_label_text(item, langs)
                            options.append({
                                'label': translation,
                                'value': item.findtext('{f}value'.format(**namespaces)).strip()
                            })
                        question.update({'options': options})
                    questions.append(question)
        build_questions(self.xml.find('{h}body'.format(**namespaces)))
        return questions