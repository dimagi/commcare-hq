"""
Code related to parsing instance('casedb') case property references in a form.

This was originally intended to include the ability to update references in all
forms when a property was renamed, but this was abandoned.  For the last state
of some work towards that, see
https://github.com/dimagi/commcare-hq/commit/584073d82e7c67f3b65ee4c51b1f7886d08a9842
"""
import re
from collections import defaultdict
from xml.etree import ElementTree

from django.utils.translation import ugettext_noop, ugettext as _

#from corehq.apps.app_manager.models import Application
from corehq.apps.app_manager.xform import XFormError
from corehq.apps.app_manager.util import (get_all_case_properties,
        ParentCasePropertyBuilder)

__all__ = ['get_references', 'get_validated_references', 'get_reftype_names'
    #'RefType', 'ModuleType'
]

# these are duplicated in formdesigner.commcare.js
PROPERTY_NAME = r"([a-zA-Z][\w_-]*)"
CASE_PROPERTY_PREFIX = r"instance('casedb')/casedb/case[@case_id=instance('commcaresession')/session/data/case_id]/"

# hack. (?!\=\s*) is a negative lookahead as a safeguard against matching
# references within other references (although we guard against that in the
# replacing too).
CASE_PROPERTY = re.compile(
    r"(?!\=\s*)" + re.escape(CASE_PROPERTY_PREFIX) + PROPERTY_NAME)

PARENT_CASE_PROPERTY_PREFIX = r"instance('casedb')/casedb/case[@case_id=instance('casedb')/casedb/case[@case_id=instance('commcaresession')/session/data/case_id]/index/parent]/"
PARENT_CASE_PROPERTY = re.compile(
    r"(?!\=\s*)" + re.escape(PARENT_CASE_PROPERTY_PREFIX) + PROPERTY_NAME)

# constants for reference types
# we don't handle non-itext messages
class RefType(object):
    SETVALUE = 'setvalue'
    RELEVANT = 'relevant'
    CONSTRAINT = 'constraint'
    CALCULATE = 'calculate'
    REPEAT_COUNT = 'repeat_count'
    LABEL_ITEXT = 'label_itext'
    CONSTRAINT_ITEXT = 'constraint_itext'
    HINT_ITEXT = 'hint_itext'

    OWN_CASE = 'own_case'
    PARENT_CASE = 'parent_case'

# same as property names in Vellum
REFTYPE_NAMES = {
    RefType.SETVALUE: ugettext_noop('Load Value'),
    RefType.RELEVANT: ugettext_noop('Display Condition'),
    RefType.CONSTRAINT: ugettext_noop('Validation Condition'),
    RefType.CALCULATE: ugettext_noop('Calculate Condition'),
    RefType.REPEAT_COUNT: ugettext_noop('Repeat Count'),
    RefType.LABEL_ITEXT: ugettext_noop('Label'),
    RefType.CONSTRAINT_ITEXT: ugettext_noop('Validation Message'),
    RefType.HINT_ITEXT: ugettext_noop('Hint Message'),
}


def get_reftype_names():
    """Get translated names for attributes that can reference a case
    property"""
    return dict([(k, _(v)) for (k, v) in REFTYPE_NAMES.items()])


def get_references(form):
    """
    Get all case property references in `xform`
    [
        {
            'question': '/data/question1',
            'case_type': RefType.OWN_CASE|RefType.PARENT_CASE,
            'property': 'foo',
            'type': RefType.FOO,
        }
    ]
    Multiple actual references of a given type return only one entry (i.e.,
    multiple references in the same condition, or multiple references in the
    same itext message in different languages).
    """
    all_references = defaultdict(list)
    def collect_parsed_references(property_value):
        # for now we don't include the raw value in the returned reference
        value = property_value.pop('value')
        question = property_value.pop('question')
        for r in parse_references(value):
            ref = dict(r, **property_value)
            # for now we don't care about multiple references to the same property in
            # the same question and attribute
            if all(ref != x for x in all_references[question]):
                all_references[question].append(ref)
        return value
    for_each_property_value(form.wrapped_xform(), collect_parsed_references)

    return dict(all_references)

def get_validated_references(form):
    references = get_references(form)

    case_type = form.get_module().case_type
    case_properties = get_all_case_properties(form.get_app())[case_type]

    for question, refs in references.items():
        for r in refs:
            if r['case_type'] == RefType.OWN_CASE:
                property = r['property']
            else:  # PARENT_CASE
                property = 'parent/%s' % r['property']
            r['valid'] = property in case_properties

    return references


def overlapping(start, end, ranges):
    return any(
        (start >= s and start < e) or
        (end > s and end <= e)
        for (s, e) in ranges
    )


def parse_references(value_string):
    # don't parse case property references within parent property references
    parent_ranges = []
    # avoid more than one reference entry per property name per case type
    parent_references = {}
    case_references = {}
    for match in re.finditer(PARENT_CASE_PROPERTY, value_string):
        parent_ranges.append((match.start(), match.end()))
        property = match.group(1)
        parent_references[property] = {
            'case_type': RefType.PARENT_CASE,
            'property': property
        }

    for match in re.finditer(CASE_PROPERTY, value_string):
        if not overlapping(match.start(), match.end(), parent_ranges):
            property = match.group(1)
            case_references[property] = {
                'case_type': RefType.OWN_CASE,
                'property': property
            }

    return ([r for (k, r) in parent_references.items()] +
            [r for (k, r) in case_references.items()])


def get_path(node, xform):
    try:
        return xform.get_path(node)
    except XFormError:
        return False


def for_each_property_value(xform, callback):
    head = xform.find('{h}head')
    model = head.find('{f}model')

    # head: setvalues
    for setvalue in head.findall('{f}setvalue'):
        question = get_path(setvalue, xform)
        value = setvalue.attrib.get('value')
        if question and value:
            setvalue.attrib['value'] = callback({
                'question': question,
                'value': value,
                'type': RefType.SETVALUE
            })

    # bind: relevant, calculate, constraint, and constraint itext
    for bind in model.findall('{f}bind'):
        question = get_path(bind, xform)
        if not question:
            continue
        relevant = bind.attrib.get('relevant')
        constraint = bind.attrib.get('constraint')
        calculate = bind.attrib.get('calculate')
        if relevant:
            bind.attrib['relevant'] = callback({
                'question': question,
                'value': relevant,
                'type': RefType.RELEVANT
            })
        if constraint:
            bind.attrib['constraint'] = callback({
                'question': question,
                'value': constraint,
                'type': RefType.CONSTRAINT
            })
        if calculate:
            bind.attrib['calculate'] = callback({
                'question': question,
                'value': calculate,
                'type': RefType.CALCULATE
            })

        constraintMsgID = bind.attrib.get('{jr}constraintMsg')
        if constraintMsgID:
            for_each_itext_value(xform, constraintMsgID,
                    lambda v: callback({
                        'question': question,
                        'value': value,
                        'type': RefType.CONSTRAINT_ITEXT
                    }))

    def node_to_refs(node, items, type):
        message_nodes = filter(None,
            [i.find(type) for i in items or []] +
            [node.find(type)]
        )
        return filter(None, [n.attrib.get('ref') for n in message_nodes])

    # control: label and hint itext, repeat count
    for node_data in xform.get_control_nodes(include_triggers=True):
        node, path, repeat_context, items, _ = node_data
        jr_count = node.attrib.get('{jr}count')
        if jr_count:
            node.attrib['{jr}count'] = callback({
                'question': path,
                'value': jr_count,
                'type': RefType.REPEAT_COUNT
            })

        for itext_ref in node_to_refs(node, items, '{f}label'):
            for_each_itext_value(xform, itext_ref,
                    lambda v: callback({
                        'question': path,
                        'value': v,
                        'type': RefType.LABEL_ITEXT
                    }))
        for itext_ref in node_to_refs(node, items, '{f}hint'):
            for_each_itext_value(xform, itext_ref,
                    lambda v: callback({
                        'question': path,
                        'value': v,
                        'type': RefType.HINT_ITEXT
                    }))


def for_each_itext_value(xform, itext_ref, callback):
    # jr:itext('foo') -> foo
    try:
        itext_id = itext_ref[10:-2]
    except IndexError:
        return

    items = xform.model_node.findall(
            '{f}itext/{f}translation/{f}text[@id="%s"]' % itext_id)
    for item in items:
        for i, value in enumerate(item.findall('{f}value')):
            # unwrap and stringify
            callback(ElementTree.tostring(value.xml))
