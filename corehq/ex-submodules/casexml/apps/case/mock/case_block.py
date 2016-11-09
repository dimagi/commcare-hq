import copy
from datetime import datetime, date
import numbers
from xml.etree import ElementTree
from casexml.apps.case.xml import V2_NAMESPACE
from dimagi.utils.parsing import json_format_datetime
from collections import namedtuple
from functools import partial


IndexAttrs = namedtuple('IndexAttrs', ['case_type', 'case_id', 'relationship'])
ChildIndexAttrs = partial(IndexAttrs, relationship='child')


class CaseBlock(object):
    """
    see https://github.com/dimagi/commcare/wiki/casexml20 for spec
    """
    undefined = object()

    def __init__(self, case_id, date_modified=None, user_id=undefined,
                 owner_id=undefined, external_id=undefined, case_type=undefined,
                 case_name=undefined, create=False, date_opened=undefined, update=None,
                 close=False, index=None):

        now = datetime.utcnow()
        self.date_modified = date_modified or now
        if date_opened == CaseBlock.undefined and create:
            self.date_opened = now.date()
        else:
            self.date_opened = date_opened
        self.update = copy.copy(update) if update else {}
        if index:
            self.index = {key: self._make_index_attrs(value)
                          for key, value in index.items()}
        else:
            self.index = {}

        if create:
            self.case_type = "" if case_type is CaseBlock.undefined else case_type
            self.case_name = "" if case_name is CaseBlock.undefined else case_name
            self.owner_id = "" if owner_id is CaseBlock.undefined else owner_id
        else:
            self.case_type = case_type
            self.case_name = case_name
            self.owner_id = owner_id

        self.close = close
        self.case_id = case_id
        self.user_id = user_id
        self.external_id = external_id
        self.create = create
        self._json_repr = self._to_json()

    @staticmethod
    def _make_index_attrs(value):
        if len(value) == 2:
            return IndexAttrs(value[0], value[1], 'child')
        else:
            return IndexAttrs(value[0], value[1], value[2])

    def _to_json(self):
        result = {}
        if self.create:
            result['create'] = {}
        result['update'] = self.update

        create_or_update = {
            'case_type': self.case_type,
            'case_name': self.case_name,
        }

        result.update({
            '_attrib': {
                'case_id': self.case_id,
                'date_modified': self.date_modified,
                'user_id': self.user_id,
                'xmlns': V2_NAMESPACE,
            }
        })
        if self.owner_id is not None:
            create_or_update.update({
                'owner_id': self.owner_id,
            })
        result['update'].update({
            'external_id': self.external_id,
            'date_opened': self.date_opened,
        })

        # fail if user specifies both, say, case_name='Johnny' and update={'case_name': 'Johnny'}
        for key in create_or_update:
            if create_or_update[key] is not CaseBlock.undefined and key in result['update']:
                raise CaseBlockError("Key %r specified twice" % key)

        create_or_update = {key: val for key, val in create_or_update.items()
                            if val is not CaseBlock.undefined}
        if self.create:
            result['create'].update(create_or_update)
        else:
            result['update'].update(create_or_update)

        if self.close:
            result['close'] = {}

        if all(val is CaseBlock.undefined for val in result['update'].values()):
                result['update'] = CaseBlock.undefined

        if self.index:
            result['index'] = {}
            for name in self.index.keys():
                print name
                self.case_type = self.index[name].case_type
                self.case_id = self.index[name].case_id

                # relationship = "child" for index to a parent case (default)
                # relationship = "extension" for index to a host case
                relationship = self.index[name].relationship
                if relationship not in ('child', 'extension'):
                    raise CaseBlockError('Valid values for an index relationship are "child" and "extension"')
                _attrib = {'case_type': self.case_type}
                if relationship != 'child':
                    _attrib['relationship'] = relationship
                result['index'][name] = {
                    '_attrib': _attrib,
                    '_text': self.case_id
                }
        return result

    def as_xml(self, format_datetime=None):
        format_datetime = format_datetime or json_format_datetime
        case = ElementTree.Element('case')
        order = ['case_id', 'date_modified', 'create', 'update', 'close',
                 'case_type', 'user_id', 'case_name', 'external_id', 'owner_id', 'date_opened']

        def sort_key(item):
            word, _ = item
            try:
                i = order.index(word)
                return 0, i
            except ValueError:
                return 1, word

        def fmt(value):
            if value is None:
                return ''
            if isinstance(value, datetime):
                return unicode(format_datetime(value))
            elif isinstance(value, (basestring, numbers.Number, date)):
                return unicode(value)
            else:
                raise CaseBlockError("Can't transform to XML: {}; unexpected type {}.".format(value, type(value)))

        def dict_to_xml(block, dct):
            if '_attrib' in dct:
                for (key, value) in dct['_attrib'].items():
                    if value is not CaseBlock.undefined:
                        block.set(key, fmt(value))
            if '_text' in dct:
                block.text = unicode(dct['_text'])

            for (key, value) in sorted(dct.items(), key=sort_key):
                if value is not CaseBlock.undefined and not key.startswith('_'):
                    elem = ElementTree.Element(key)
                    block.append(elem)
                    if isinstance(value, dict):
                        dict_to_xml(elem, value)
                    else:
                        elem.text = fmt(value)
        dict_to_xml(case, self._json_repr)
        return case

    def as_string(self, format_datetime=None):
        return ElementTree.tostring(self.as_xml(format_datetime))


class CaseBlockError(Exception):
    pass
