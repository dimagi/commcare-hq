from __future__ import absolute_import
from __future__ import unicode_literals
import copy
import numbers
import warnings
from datetime import datetime, date
from xml.etree import cElementTree as ElementTree
from casexml.apps.case.xml import V2_NAMESPACE
from dimagi.utils.parsing import json_format_datetime, string_to_datetime
from collections import namedtuple
from functools import partial
import six

# relationship = "child" for index to a parent case (default)
# relationship = "extension" for index to a host case
IndexAttrs = namedtuple('IndexAttrs', ['case_type', 'case_id', 'relationship'])
ChildIndexAttrs = partial(IndexAttrs, relationship='child')


class CaseBlock(object):
    """
    see https://github.com/dimagi/commcare/wiki/casexml20 for spec
    """
    undefined = object()
    _built_ins = {'case_type', 'case_name', 'owner_id'}

    def __init__(self, case_id, date_modified=None, user_id=undefined,
                 owner_id=undefined, external_id=undefined, case_type=undefined,
                 case_name=undefined, create=False, date_opened=undefined, update=None,
                 close=False, index=None, strict=True):
        if isinstance(case_id, bytes):
            case_id = case_id.decode('utf-8')
        if isinstance(user_id, bytes):
            user_id = user_id.decode('utf-8')
        # todo: can we use None instead of CaseBlock.undefined, throughout?
        owner_id = CaseBlock.undefined if owner_id is None else owner_id
        self.update = copy.copy(update) if update else {}
        now = datetime.utcnow()
        self.date_modified = date_modified or now
        self.date_opened = (now.date() if create and date_opened is CaseBlock.undefined
                            else date_opened)

        self.case_type = "" if create and case_type is CaseBlock.undefined else case_type
        self.case_name = "" if create and case_name is CaseBlock.undefined else case_name
        self.owner_id = "" if create and owner_id is CaseBlock.undefined else owner_id
        self.close = close
        self.case_id = case_id
        self.user_id = user_id
        self.external_id = external_id
        self.create = create
        if strict:
            self._check_for_duplicate_properties()
        self.index = {key: self._make_index_attrs(value)
                      for key, value in index.items()} if index else {}

    def __repr__(self):
        return (
            "CaseBlock("
            "case_id='{self.case_id}', "
            "case_type='{self.case_type}', "
            "case_name='{self.case_name}', "
            "owner_id='{owner_id}', "
            "state='{state}'"
            ")"
        ).format(
            self=self,
            state="closed" if self.close else "open",
            owner_id=self.owner_id if self.owner_id is not CaseBlock.undefined else "",
        )

    def _updatable_built_ins(self):
        return [(name, getattr(self, name)) for name in self._built_ins]

    def _check_for_duplicate_properties(self):
        for property_name, passed_value in self._updatable_built_ins():
            if passed_value is not CaseBlock.undefined and property_name in self.update:
                raise CaseBlockError("Key '{}' specified twice".format(property_name))

    @staticmethod
    def _make_index_attrs(value):
        if len(value) == 2:
            return IndexAttrs(value[0], value[1], 'child')
        else:
            case_type, case_id, relationship = value
            if relationship not in ('child', 'extension'):
                raise CaseBlockError('Valid values for an index relationship are "child" and "extension"')
            return IndexAttrs(case_type, case_id, relationship)

    def _to_json(self):
        result = {
            '_attrib': {
                'case_id': self.case_id,
                'date_modified': self.date_modified,
                'user_id': self.user_id,
                'xmlns': V2_NAMESPACE,
            },
            'update': self.update,
        }

        result['update'].update({
            'external_id': self.external_id,
            'date_opened': self.date_opened,
        })

        create_or_update = {key: val for key, val in self._updatable_built_ins()
                            if val is not CaseBlock.undefined}
        if self.create:
            result['create'] = create_or_update
        else:
            result['update'].update(create_or_update)

        if self.close:
            result['close'] = {}

        if all(val is CaseBlock.undefined for val in result['update'].values()):
                result['update'] = CaseBlock.undefined

        if self.index:
            result['index'] = {}
            for name in self.index.keys():
                case_type = self.index[name].case_type
                case_id = self.index[name].case_id

                relationship = self.index[name].relationship
                _attrib = {'case_type': case_type}
                if relationship != 'child':
                    _attrib['relationship'] = relationship
                result['index'][name] = {
                    '_attrib': _attrib,
                    '_text': case_id
                }
        return result

    def as_xml(self):
        case = ElementTree.Element('case')
        _dict_to_xml(case, self._to_json(), order=[
            'case_id', 'date_modified', 'create', 'update', 'close', 'case_type',
            'user_id', 'case_name', 'external_id', 'owner_id', 'date_opened'])
        return case

    @classmethod
    def from_xml(cls, case):

        def tag_of(node):
            if node.tag.startswith(NS):
                return node.tag.replace(NS, '')
            return node.tag

        def index_tuple(node):
            attrs = IndexAttrs(
                node.get("case_type"),
                node.text,
                node.get("relationship") or 'child',
            )
            return tag_of(node), attrs

        NS = "{%s}" % V2_NAMESPACE
        updates = {}
        fields = {"update": updates}
        for node in case.find(NS + "create") or []:
            tag = tag_of(node)
            if tag in cls._built_ins:
                fields[tag] = node.text
            # can create node have date_opened child node?
        for node in case.find(NS + "update") or []:
            tag = tag_of(node)
            if tag in cls._built_ins or tag == "external_id":
                fields[tag] = node.text
            elif tag == "date_opened":
                fields[tag] = string_to_datetime(node.text).replace(tzinfo=None)
            else:
                # can this be a hierarchical structure? if yes, how to decode?
                updates[tag] = node.text
        return cls(
            case_id=case.get("case_id"),
            date_modified=string_to_datetime(
                case.get("date_modified")).replace(tzinfo=None),
            user_id=case.get("user_id"),
            index=dict(index_tuple(x) for x in case.find(NS + "index") or []),
            **fields
        )

    def as_text(self):
        return self.as_bytes().decode('utf-8')

    def as_bytes(self):
        return ElementTree.tostring(self.as_xml())

    def as_string(self):
        warnings.warn(
            "CaseBlock.as_string is deprecated. Use CaseBlock.as_bytes or CaseBlock.as_text instead.",
            DeprecationWarning,
        )
        return self.as_bytes()


class CaseBlockError(Exception):
    pass


class _DictToXML(object):
    def __init__(self, order):
        self.order = order

    def build(self, block, dct):
        if '_attrib' in dct:
            for (key, value) in dct['_attrib'].items():
                if value is not CaseBlock.undefined:
                    block.set(key, self.fmt(value))
        if '_text' in dct:
            block.text = six.text_type(dct['_text'])

        for (key, value) in sorted(list(dct.items()), key=self.sort_key):
            if value is not CaseBlock.undefined and not key.startswith('_'):
                elem = ElementTree.Element(key)
                block.append(elem)
                if isinstance(value, dict):
                    self.build(elem, value)
                else:
                    elem.text = self.fmt(value)

    def sort_key(self, item):
        word, _ = item
        try:
            i = self.order.index(word)
            return 0, i
        except ValueError:
            return 1, word

    @staticmethod
    def fmt(value):
        if value is None:
            return ''
        if isinstance(value, datetime):
            return six.text_type(json_format_datetime(value))
        elif isinstance(value, bytes):
            return value.decode('utf-8')
        elif isinstance(value, six.text_type):
            return value
        elif isinstance(value, (numbers.Number, date)):
            return six.text_type(value)
        else:
            raise CaseBlockError("Can't transform to XML: {}; unexpected type {}.".format(value, type(value)))


def _dict_to_xml(block, dct, order):
    return _DictToXML(order).build(block, dct)
