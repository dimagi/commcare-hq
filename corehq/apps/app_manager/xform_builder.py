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
>>> xform.add_question('name', 'What is your name?')
>>> xform.add_question('fav_color', u'Quelle est ta couleur préférée?',
...                    choices={'r': 'Rot', 'g': u'Grün', 'b': 'Blau'})
>>> xml = xform.tostring(pretty_print=True, encoding='utf-8')
>>> xml.startswith(
... '''<h:html xmlns:h="http://www.w3.org/1999/xhtml" '''
...         '''xmlns:orx="http://openrosa.org/jr/xforms" '''
...         '''xmlns="http://www.w3.org/2002/xforms" '''
...         '''xmlns:xsd="http://www.w3.org/2001/XMLSchema" '''
...         '''xmlns:jr="http://openrosa.org/javarosa">\\n'''
... '''    <h:head>\\n'''
... '''        <h:title>Built by XFormBuilder</h:title>\\n'''
... '''        <model>\\n'''
... '''            <instance>\\n'''
... '''                <data xmlns:jrm="http://dev.commcarehq.org/jr/xforms" '''
...                       '''xmlns="http://openrosa.org/formdesigner/''')  # Skip the random xmlns.
True
>>> xml.endswith('''" '''
...                       '''uiVersion="1" '''
...                       '''version="3" '''
...                       '''name="Built by XFormBuilder">'''
...                     '''<name/>'''
...                     '''<fav_color/>'''
...                 '''</data>\\n'''
... '''            </instance>\\n'''
... '''            <itext>\\n'''
... '''                <translation lang="en" default="">'''
...                     '''<text id="name-label">'''
...                         '''<value>What is your name?</value>'''
...                     '''</text>'''
...                     '''<text id="fav_color-label">'''
...                         '''<value>'''
...                             '''Quelle est ta couleur pr\xc3\x83\xc2\xa9f\xc3\x83\xc2\xa9r\xc3\x83\xc2\xa9e?'''
...                         '''</value>'''
...                     '''</text>'''
...                     '''<text id="fav_color-r-label">'''
...                         '''<value>Rot</value>'''
...                     '''</text>'''
...                     '''<text id="fav_color-b-label">'''
...                         '''<value>Blau</value>'''
...                     '''</text>'''
...                     '''<text id="fav_color-g-label">'''
...                         '''<value>Gr\xc3\x83\xc2\xbcn</value>'''
...                     '''</text>'''
...                 '''</translation>\\n'''
... '''            </itext>\\n'''
...     '''        <bind nodeset="/data/name" type="xsd:string"/>'''
...             '''<bind nodeset="/data/fav_color" type="xsd:string"/>'''
...         '''</model>\\n'''
... '''    </h:head>\\n'''
... '''    <h:body>'''
...         '''<input ref="/data/name"><label ref="jr:itext(\'name-label\')"/></input>'''
...         '''<input ref="/data/fav_color"><label ref="jr:itext(\'fav_color-label\')"/></input>'''
...     '''</h:body>\\n'''
... '''</h:html>\\n'''
... )
True

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
        if source is None:
            xmlns = 'http://openrosa.org/formdesigner/{}'.format(uuid.uuid4())
            self._etree = etree.XML(EMPTY_XFORM.format(name=name, xmlns=xmlns))
            self.ns['d'] = xmlns
            self._data = self._etree.xpath('./h:head/x:model/x:instance/d:data', namespaces=self.ns)[0]
        else:
            self._etree = etree.fromstring(source)
            # We don't know the data node's namespace, so we can't just fetch it with xpath.
            instance = self._etree.xpath('./h:head/x:model/x:instance', namespaces=self.ns)[0]
            self._data = [e for e in instance if e.tag == 'data'][0]
            self.ns['d'] = self._data.nsmap[None]
        self._translation1 = self._etree.xpath('./h:head/x:model/x:itext/x:translation', namespaces=self.ns)[0]
        self._model = self._etree.xpath('./h:head/x:model', namespaces=self.ns)[0]
        self._body = self._etree.xpath('./h:body', namespaces=self.ns)[0]

    def tostring(self, **kwargs):
        return etree.tostring(self._etree, **kwargs)

    def add_question(self, name, label, data_type='string', group=None, choices=None):
        """
        Adds a question to the XForm.

        Assumes that questions are added in a sane order. You can't add a
        question to a group before you add the group.

        :param name: Question name
        :param label: Question label
        :param data_type: The type of the question
        :param group: The name of the question's group, or an iterable of names if nesting is deeper than one
        :param choices: A dictionary of {name: label} pairs
        """
        if data_type not in ('string', 'int', 'double', 'date', 'time', 'dateTime', 'select', 'select1', 'group',
                             'repeatGroup'):
            raise TypeError('Unknown question data type "{}"'.format(data_type))
        if group is not None and not isinstance(group, basestring) and not hasattr(group, '__iter__'):
            raise TypeError('group parameter needs to be a string or iterable')
        self._append_to_data(name, group)
        self._append_to_translation(name, label, group, choices)
        self._append_to_model(name, data_type, group)
        self._append_to_body(name, data_type, group, choices)

    @staticmethod
    def groups_path(groups, ns=None):
        """
        Join groups with "/", and prefix with namespace if given.

        >>> XFormBuilder.groups_path(('foo', 'bar', 'baz'), ns='x')
        'x:foo/x:bar/x:baz'
        >>> XFormBuilder.groups_path('foo', ns='x')
        'x:foo'
        >>> XFormBuilder.groups_path(('foo', 'bar', 'baz'))
        'foo/bar/baz'

        """
        if isinstance(groups, basestring):
            groups = [groups]
        if ns is None:
            return '/'.join(groups)
        return '/'.join(['{}:{}'.format(ns, g) for g in groups])

    @staticmethod
    def get_text_id(name, group=None, choice_name=None):
        """
        Builds a text node "id" parameter

        >>> XFormBuilder.get_text_id('foo')
        'foo-label'
        >>> XFormBuilder.get_text_id('foo', 'bar')
        'bar/foo-label'
        >>> XFormBuilder.get_text_id('foo', ('bar', 'baz'))
        'bar/baz/foo-label'
        >>> XFormBuilder.get_text_id('foo', ('bar', 'baz'), 'choice1')
        'bar/baz/foo-choice1-label'

        """
        text_id = []
        if group:
            text_id.append(XFormBuilder.groups_path(group) + '/')
        text_id.append(name)
        if choice_name is not None:
            text_id.append('-{}'.format(choice_name))
        text_id.append('-label')
        return ''.join(text_id)

    @staticmethod
    def get_data_ref(name, group=None):
        """
        Returns the reference to the data node of the given question

        >>> XFormBuilder.get_data_ref('foo')
        '/data/foo'
        >>> XFormBuilder.get_text_id('foo', 'bar')
        '/data/bar/foo'
        >>> XFormBuilder.get_data_ref('foo', ('bar', 'baz'))
        '/data/bar/baz/foo'

        """
        if group is None:
            return '/data/' + name
        return '/data/{}/{}'.format(XFormBuilder.groups_path(group), name)

    def _append_to_data(self, name, group=None):
        if group:
            node = self._data.xpath('./' + self.groups_path(group))[0]
        else:
            node = self._data
        node.append(etree.Element(name))

    def _append_to_translation(self, name, label, group=None, choices=None):

        def get_text_node(name_, label_, group_=None, choice_name_=None):
            return E.text(
                {'id': self.get_text_id(name_, group_, choice_name_)},
                E.value(label_)
            )

        self._translation1.append(get_text_node(name, label, group))
        if choices:
            for choice_name, choice_label in choices.items():
                self._translation1.append(get_text_node(name, choice_label, group, choice_name))

    def _append_to_model(self, name, data_type, group=None):
        if data_type in ('string', 'int', 'double', 'date', 'time', 'dateTime'):
            bind = E.bind({'nodeset': self.get_data_ref(name, group),
                           'type': 'xsd:' + data_type})
        else:
            bind = E.bind({'nodeset': self.get_data_ref(name, group)})
        self._model.append(bind)

    def _append_to_body(self, name, data_type, group=None, choices=None):

        def walk_groups(node_, groups, data_ref='/data'):
            """
            The structure of repeating and non-repeating groups is different.
            Walk a list of groups and return the node of the last one.
            """
            group_ = groups.pop(0)
            data_ref = '{}/{}'.format(data_ref, group_)
            try:
                # Is it a repeat group?
                group_node = node_.xpath('./group/repeat[@nodeset="{}"]'.format(data_ref))[0]
            except IndexError:
                # It must be a normal group
                group_node = node_.xpath('./group[@ref="{}"]'.format(data_ref))[0]
            if not groups:
                return group_node
            return walk_groups(group_node, groups, data_ref)

        def get_group_question_node(name_, group_=None, choices_=None):
            """
            Returns a question node for a non-repeating group

            >>> node = get_group_question_node('non-repeating_group')
            >>> etree.tostring(node)
            '<group ref="/data/non-repeating_group"><label ref="jr:itext('non-repeating_group-label')" /></group>'

            """
            return E.group(
                {'ref': self.get_data_ref(name_, group_)},
                E.label({'ref': "jr:itext('{}')".format(self.get_text_id(name_, group_))})
            )

        def get_repeat_group_question_node(name_, group_=None, choices_=None):
            """
            Returns a question node for a repeat group

            >>> node = get_repeat_group_question_node('repeat_group')
            >>> etree.tostring(node)
            '<group><label ref="jr:itext(\'repeat_group-label\')"/><repeat nodeset="/data/repeat_group"/></group>'

            """
            return E.group(
                E.label({'ref': "jr:itext('{}')".format(self.get_text_id(name_, group_))}),
                E.repeat({'nodeset': self.get_data_ref(name_, group_)})
            )

        def _get_any_select_question_node(tag, name_, group_=None, choices_=None):
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
            node_ = etree.Element(tag, {'ref': self.get_data_ref(name_, group_)})
            node_.append(E.label({'ref': "jr:itext('{}')".format(self.get_text_id(name_, group_))}))
            for choice_name in choices_.keys():
                node_.append(
                    E.item(
                        E.label({'ref': "jr:itext('{}')".format(self.get_text_id(name_, group_, choice_name))}),
                        E.value(choice_name)
                    )
                )
            return node_

        def get_select_question_node(name_, group_=None, choices_=None):
            """
            Return a question node for a multiple-select multiple choice question
            """
            return _get_any_select_question_node('select', name_, group_=None, choices_=None)

        def get_select1_question_node(name_, group_=None, choices_=None):
            """
            Return a question node for a single-select multiple choice question
            """
            return _get_any_select_question_node('select1', name_, group_=None, choices_=None)

        def get_input_question_node(name_, group_=None, choices_=None):
            """
            Return a question node for a normal question

            >>> node = get_input_question_node('text_question')
            >>> etree.tostring(node)
            '<input ref="/data/text_question"><label ref="jr:itext(\'text_question-label\')"/></input>'

            """
            node_ = etree.Element('input', {'ref': self.get_data_ref(name_, group_)})
            node_.append(etree.Element('label', {'ref': "jr:itext('{}')".format(self.get_text_id(name_, group_))}))
            return node_

        if group:
            if isinstance(group, basestring):
                group = [group]
            node = walk_groups(self._body, group)
        else:
            node = self._body
        func = {
            'group': get_group_question_node,
            'repeatGroup': get_repeat_group_question_node,
            'select': get_select_question_node,
            'select1': get_select1_question_node,
        }.get(data_type, get_input_question_node)
        question_node = func(name, group, choices)
        node.append(question_node)
