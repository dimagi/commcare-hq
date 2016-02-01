# coding: utf-8
"""
XFormBuilder is intended to be a simple way to create an XForm, and add
questions to it.

It was created for importing a CDISC ODM document as a CommCare app.
Third-party solutions lacked important features like nested groups, and most
required their input to come via an Excel spreadsheet or JSON, which did not
seem to be a good fit.


>>> from corehq.apps.app_manager.xform_builder import XFormBuilder
>>> xform = XFormBuilder('Built by XFormBuilder')
>>> _ = xform.new_question('name', 'What is your name?')
>>> group = xform.new_group('personal', 'Personal Questions')
>>> _ = group.new_question('fav_color', u'Quelle est ta couleur préférée?',
...                        choices={'r': 'Rot', 'g': u'Grün', 'b': 'Blau'})
>>> xml = xform.tostring(pretty_print=True, encoding='utf-8', xml_declaration=True)


"""
import uuid
from lxml import etree
from lxml.builder import E

EMPTY_XFORM = """<?xml version="1.0"?>
<h:html xmlns:h="http://www.w3.org/1999/xhtml"
        xmlns:orx="http://openrosa.org/jr/xforms"
        xmlns="http://www.w3.org/2002/xforms"
        xmlns:xsd="http://www.w3.org/2001/XMLSchema"
        xmlns:jr="http://openrosa.org/javarosa">
    <h:head>
        <h:title>{name}</h:title>
        <model>
            <instance>
                <data xmlns:jrm="http://dev.commcarehq.org/jr/xforms"
                      xmlns="{xmlns}"
                      uiVersion="1"
                      version="3"
                      name="{name}"/>
            </instance>
            <itext>
                <translation lang="en" default=""/>
            </itext>
        </model>
    </h:head>
    <h:body/>
</h:html>"""


# The subset of ODK data types that are XSD data types
# cf. http://www.w3.org/TR/xmlschema-2/#built-in-datatypes
XSD_TYPES = ('string', 'int', 'boolean', 'decimal', 'date', 'time', 'dateTime')
# The data types supported by the Open Data Kit XForm spec
# cf. https://opendatakit.github.io/odk-xform-spec/#data-types
ODK_TYPES = XSD_TYPES + ('select', 'select1', 'geopoint', 'geotrace', 'geoshape', 'binary', 'barcode')
# CommCare question group types
GROUP_TYPES = ('group', 'repeatGroup')  # TODO: Support 'questionList'


class XFormBuilder(object):
    """
    A utility class for adding questions to an XForm
    """

    def __init__(self, name='Untitled Form', source=None):
        """
        Initialises an XFormBuilder instance

        If source is not given, initialises an empty XForm, and sets
        name/title to name parameter.

        If source is given then initialises from source, ignores name
        parameter. Assumes that source includes a data node.
        """
        self.ns = {
            'h': "http://www.w3.org/1999/xhtml",
            'orx': "http://openrosa.org/jr/xforms",
            'x': "http://www.w3.org/2002/xforms",
            'xsd': "http://www.w3.org/2001/XMLSchema",
            'jr': "http://openrosa.org/javarosa",
            'jrm': "http://dev.commcarehq.org/jr/xforms",
        }
        strip_spaces = etree.XMLParser(remove_blank_text=True)
        if source is None:
            xmlns = 'http://openrosa.org/formdesigner/{}'.format(uuid.uuid4())
            self._etree = etree.XML(EMPTY_XFORM.format(name=name, xmlns=xmlns), parser=strip_spaces)
            self.ns['d'] = xmlns
            self._data = self._etree.xpath('./h:head/x:model/x:instance/d:data', namespaces=self.ns)[0]
        else:
            self._etree = etree.fromstring(source, parser=strip_spaces)
            # We don't know the data node's namespace, so we can't just fetch it with xpath.
            instance = self._etree.xpath('./h:head/x:model/x:instance', namespaces=self.ns)[0]
            self._data = [e for e in instance if e.tag == 'data'][0]
            self.ns['d'] = self._data.nsmap[None]
        self._translation1 = self._etree.xpath('./h:head/x:model/x:itext/x:translation', namespaces=self.ns)[0]
        self._model = self._etree.xpath('./h:head/x:model', namespaces=self.ns)[0]
        self._body = self._etree.xpath('./h:body', namespaces=self.ns)[0]

    @property
    def xmlns(self):
        """
        Unique XMLNS
        """
        return self.ns['d']

    def tostring(self, **kwargs):
        return etree.tostring(self._etree, **kwargs)

    def new_question(self, name, label, data_type='string', group=None, choices=None, label_safe=False, **params):
        """
        Adds a question to the XForm.

        Assumes that questions are added in a sane order. You can't add a
        question to a group before you add the group.

        :param name: Question name
        :param label: Question label
        :param data_type: The type of the question, or None for hidden values
        :param group: The name of the question's group, or an iterable of names if nesting is deeper than one
        :param choices: A dictionary of {name: label} pairs
        :param label_safe: Does the label contain (safe) XML?
        :param params: Supported question parameters: repeat_count, calculate
        :return: A Question instance, or QuestionGroup instance if `data_type` is a group type.
        """
        if data_type is not None and data_type not in ODK_TYPES + GROUP_TYPES:
            raise TypeError('Unknown question data type "{}"'.format(data_type))
        if group is not None and not isinstance(group, basestring) and not hasattr(group, '__iter__'):
            raise TypeError('group parameter needs to be a string or iterable')
        groups = [group] if isinstance(group, basestring) else group
        self._append_to_data(name, groups)
        self._append_to_model(name, data_type, groups, **params)
        if data_type is not None:
            self._append_to_translation(name, label, groups, choices, label_safe)
            self._append_to_body(name, data_type, groups, choices, **params)
        if data_type in GROUP_TYPES:
            return QuestionGroup(name, self, groups)
        return Question(name, self, groups)

    def new_group(self, name, label, data_type='group', group=None, label_safe=False, **params):
        """
        Adds and returns a question group to the XForm.

        :param name: Group name
        :param label: Group label
        :param data_type: The type of the group ("group" or "repeatGroup")
        :param group: The name or names of the group(s) that this group is inside
        :param label_safe: Does the label contain (safe) XML?
        :param params: Supported question parameters: repeat_count
        :return: A QuestionGroup instance
        """
        if data_type not in GROUP_TYPES:
            raise TypeError('Unknown question group type "{}"'.format(data_type))
        # Note: new_question returns a QuestionGroup, because data_type is a group type.
        return self.new_question(name, label, data_type, group, label_safe=label_safe, **params)

    @staticmethod
    def get_text_id(name, groups=None, choice_name=None):
        """
        Builds a text node "id" parameter

        >>> XFormBuilder.get_text_id('foo')
        'foo-label'
        >>> XFormBuilder.get_text_id('foo', ['bar'])
        'bar/foo-label'
        >>> XFormBuilder.get_text_id('foo', ['bar', 'baz'])
        'bar/baz/foo-label'
        >>> XFormBuilder.get_text_id('foo', ['bar', 'baz'], 'choice1')
        'bar/baz/foo-choice1-label'

        """
        text_id = []
        if groups:
            text_id.append('/'.join(groups) + '/')
        text_id.append(name)
        if choice_name is not None:
            text_id.append('-{}'.format(choice_name))
        text_id.append('-label')
        return ''.join(text_id)

    @staticmethod
    def get_data_ref(name, groups=None):
        """
        Returns the reference to the data node of the given question

        >>> XFormBuilder.get_data_ref('foo')
        '/data/foo'
        >>> XFormBuilder.get_data_ref('foo', ['bar'])
        '/data/bar/foo'
        >>> XFormBuilder.get_data_ref('foo', ['bar', 'baz'])
        '/data/bar/baz/foo'

        """
        if groups is None:
            return '/data/' + name
        return '/data/{}/{}'.format('/'.join(groups), name)

    def _append_to_data(self, name, groups=None):
        if groups:
            node = self._data.xpath('./' + '/'.join(groups))[0]
        else:
            node = self._data
        node.append(etree.Element(name))

    def _append_to_translation(self, name, label, group=None, choices=None, label_safe=False):

        def get_text_node(name_, label_, group_=None, choice_name_=None, label_safe_=False):
            if label_safe_:
                return E.text(
                    {'id': self.get_text_id(name_, group_, choice_name_)},
                    etree.fromstring('<value>{}</value>'.format(label_))
                )
            return E.text(
                {'id': self.get_text_id(name_, group_, choice_name_)},
                E.value(label_)
            )

        self._translation1.append(get_text_node(name, label, group, label_safe_=label_safe))
        if choices:
            for choice_name, choice_label in choices.items():
                self._translation1.append(get_text_node(name, choice_label, group, choice_name, label_safe))

    def _append_to_model(self, name, data_type, group=None, **params):
        if data_type is None or data_type in XSD_TYPES:
            attrs = {'nodeset': self.get_data_ref(name, group)}
            if data_type in XSD_TYPES:
                attrs['type'] = 'xsd:' + data_type
            if 'calculate' in params:
                attrs['calculate'] = params['calculate']
            self._model.append(E.bind(attrs))

    def _append_to_body(self, name, data_type, groups=None, choices=None, **params):

        def walk_groups(node_, groups_, data_ref='/data'):
            """
            The structure of repeating and non-repeating groups is different.
            Walk a list of groups and return the node of the last one.
            """
            groups_ = list(groups_)  # groups_ is passed by ref. Don't modify original.
            group_ = groups_.pop(0)
            data_ref = '{}/{}'.format(data_ref, group_)
            try:
                # Is it a repeat group?
                group_node = node_.xpath('./group/repeat[@nodeset="{}"]'.format(data_ref))[0]
            except IndexError:
                # It must be a normal group
                group_node = node_.xpath('./group[@ref="{}"]'.format(data_ref))[0]
            if not groups_:
                return group_node
            return walk_groups(group_node, groups_, data_ref)

        def get_group_question_node(name_, groups_=None, choices_=None, **params_):
            """
            Returns a question node for a non-repeating group

            >>> node = get_group_question_node('non-repeating_group')
            >>> etree.tostring(node)
            '<group ref="/data/non-repeating_group"><label ref="jr:itext('non-repeating_group-label')" /></group>'

            """
            return E.group(
                {'ref': self.get_data_ref(name_, groups_)},
                E.label({'ref': "jr:itext('{}')".format(self.get_text_id(name_, groups_))})
            )

        def get_repeat_group_question_node(name_, groups_=None, choices_=None, **params_):
            """
            Returns a question node for a repeat group

            >>> node = get_repeat_group_question_node('repeat_group')
            >>> etree.tostring(node)
            '<group><label ref="jr:itext(\'repeat_group-label\')"/><repeat nodeset="/data/repeat_group"/></group>'

            """
            repeat_attrs = {'nodeset': self.get_data_ref(name_, groups_)}
            if 'repeat_count' in params_:
                question = params_['repeat_count']
                repeat_attrs.update({
                    '{{{jr}}}count'.format(**self.ns): self.get_data_ref(question.name, question.groups),
                    '{{{jr}}}noAddRemove'.format(**self.ns): "true()"
                })
            return E.group(
                E.label({'ref': "jr:itext('{}')".format(self.get_text_id(name_, groups_))}),
                E.repeat(repeat_attrs)
            )

        def _get_any_select_question_node(tag, name_, groups_=None, choices_=None, **params_):
            """
            Return a question node for a single- or multiple-select multiple choice question

            e.g.
                <select ref="/data/multiple_answer_multichoice">
                    <label ref="jr:itext('multiple_answer_multichoice-label')" />
                    <item>
                        <label ref="jr:itext('multiple_answer_multichoice-choice1-label')" />
                        <value>choice1</value>
                    </item>
                    <item>
                        <label ref="jr:itext('multiple_answer_multichoice-choice2-label')" />
                        <value>choice2</value>
                    </item>
                </select>
            """
            node_ = etree.Element(tag, {'ref': self.get_data_ref(name_, groups_)})
            node_.append(E.label({'ref': "jr:itext('{}')".format(self.get_text_id(name_, groups_))}))
            for choice_name in choices_.keys():
                node_.append(
                    E.item(
                        E.label({'ref': "jr:itext('{}')".format(self.get_text_id(name_, groups_, choice_name))}),
                        E.value(choice_name if isinstance(choice_name, basestring) else str(choice_name))
                    )
                )
            return node_

        def get_select_question_node(name_, groups_=None, choices_=None, **params_):
            """
            Return a question node for a multiple-select multiple choice question
            """
            return _get_any_select_question_node('select', name_, groups_, choices_, **params_)

        def get_select1_question_node(name_, groups_=None, choices_=None, **params_):
            """
            Return a question node for a single-select multiple choice question
            """
            return _get_any_select_question_node('select1', name_, groups_, choices_, **params_)

        def get_input_question_node(name_, groups_=None, choices_=None, **params_):
            """
            Return a question node for a normal question

            >>> node = get_input_question_node('text_question')
            >>> etree.tostring(node)
            '<input ref="/data/text_question"><label ref="jr:itext(\'text_question-label\')"/></input>'

            """
            return E.input(
                {'ref': self.get_data_ref(name_, groups_)},
                E.label({'ref': "jr:itext('{}')".format(self.get_text_id(name_, groups_))})
            )

        if groups:
            node = walk_groups(self._body, groups)
        else:
            node = self._body
        func = {
            'group': get_group_question_node,
            'repeatGroup': get_repeat_group_question_node,
            'select': get_select_question_node,
            'select1': get_select1_question_node,
        }.get(data_type, get_input_question_node)
        question_node = func(name, groups, choices, **params)
        node.append(question_node)


class Question(object):

    def __init__(self, name, xform, groups=None):
        self.name = name
        self.xform = xform
        self.groups = groups


class QuestionGroup(object):

    def __init__(self, name, xform, parents=None):
        self.name = name
        self.xform = xform
        self.groups = [name] if parents is None else list(parents) + [name]

    def new_question(self, name, label, data_type='string', choices=None, label_safe=False, **params):
        return self.xform.new_question(name, label, data_type, self.groups, choices, label_safe, **params)

    def new_group(self, name, label, data_type='group', label_safe=False, **params):
        return self.xform.new_group(name, label, data_type, self.groups, label_safe, **params)
