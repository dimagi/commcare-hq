import copy
from datetime import datetime, date
import numbers
from xml.etree import ElementTree
from casexml.apps.case.xml import NS_VERSION_MAP, V2
from dimagi.utils.parsing import json_format_datetime


class CaseBlock(dict):
    undefined = object()

    def __init__(self,
            case_id,
            date_modified=None,
            user_id=undefined,
            owner_id=undefined,
            external_id=undefined,
            case_type=undefined,
            case_name=undefined,
            create=False,
            date_opened=undefined,
            update=None,
            close=False,
            index=None,
            strict=True,
        ):
        """
        https://github.com/dimagi/commcare/wiki/casexml20

        <case xmlns="http://commcarehq.org/case/transaction/v2" case_id="" user_id="" date_modified="" >
            <!-- user_id - At Most One: the GUID of the user responsible for this transaction -->
            <!-- case_id - Exactly One: The id of the abstract case to be modified (even in the case of creation) -->
            <!-- date_modified - Exactly One: The date and time of this operation -->
            <create>         <!-- At Most One: Create action -->
                <case_type/>             <!-- Exactly One: The ID for the type of case represented -->
                <owner_id/>                 <!-- At Most One: The GUID of the current owner of this case -->
                <case_name/>                <!-- Exactly One: A semantically meaningless but human readable name associated with the case -->
            </create>
            <update>         <!-- At Most One: Updates data for the case -->
                <case_type/>             <!-- At Most One: Modifies the Case Type for the case -->
                <case_name/>                <!-- At Most One: A semantically meaningless but human  readable name associated with the case -->
                <date_opened/>              <!-- At Most One: Modifies the Date the case was opened -->
                <owner_id/>                 <!-- At Most One: Modifies the owner of this case -->
                <*/>                        <-- An Arbitrary Number: Creates or mutates a value  identified by the key provided -->
            </update>
            <index/>          <!-- At Most One: Contains a set of referenced GUID's to other cases -->
            <close/>          <!-- At Most One: Closes the case -->
         </case>

        """
        super(CaseBlock, self).__init__()
        self._id = case_id
        now = datetime.utcnow()
        date_modified = date_modified or now
        if date_opened == CaseBlock.undefined and create:
            date_opened = now.date()
        update = copy.copy(update) if update else {}
        index = copy.copy(index) if index else {}

        self.XMLNS = NS_VERSION_MAP.get(V2)

        self.VERSION = V2
        self.CASE_TYPE = "case_type"

        if create:
            self['create'] = {}
            # make case_type
            case_type = "" if case_type is CaseBlock.undefined else case_type
            case_name = "" if case_name is CaseBlock.undefined else case_name
            owner_id = "" if owner_id is CaseBlock.undefined else owner_id
        self['update'] = update

        create_or_update = {
            self.CASE_TYPE:                 case_type,
            'case_name':                    case_name,
        }

        self.update({
            '_attrib': {
                'case_id':              case_id,
                'date_modified':        date_modified,
                'user_id':              user_id,
                'xmlns':                self.XMLNS,
            }
        })
        if owner_id is not None:
            create_or_update.update({
                'owner_id':                 owner_id,
            })
        self['update'].update({
            'external_id':              external_id,
            'date_opened':              date_opened,
        })

        # fail if user specifies both, say, case_name='Johnny' and update={'case_name': 'Johnny'}
        if strict:
            for key in create_or_update:
                if create_or_update[key] is not CaseBlock.undefined and key in self['update']:
                    raise CaseBlockError("Key %r specified twice" % key)

        create_or_update = {key: val for key, val in create_or_update.items() if val is not CaseBlock.undefined}
        if create:
            self['create'].update(create_or_update)
        else:
            self['update'].update(create_or_update)

        if close:
            self['close'] = {}

        if not ['' for val in self['update'].values() if val is not CaseBlock.undefined]:
                self['update'] = CaseBlock.undefined
        if index:
            self['index'] = {}
            for name in index.keys():
                case_type = index[name][0]
                case_id = index[name][1]
                # relationship = "child" for index to a parent case (default)
                # relationship = "extension" for index to a host case
                relationship = index[name][2] if len(index[name]) > 2 else 'child'
                if relationship not in ('child', 'extension'):
                    raise CaseBlockError('Valid values for an index relationship are "child" and "extension"')
                _attrib = {'case_type': case_type}
                if relationship != 'child':
                    _attrib['relationship'] = relationship
                self['index'][name] = {
                    '_attrib': _attrib,
                    '_text': case_id
                }

    def as_xml(self, format_datetime=None):
        format_datetime = format_datetime or json_format_datetime
        case = ElementTree.Element('case')
        order = ['case_id', 'date_modified', 'create', 'update', 'close',
                 self.CASE_TYPE, 'user_id', 'case_name', 'external_id', 'owner_id', 'date_opened']

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
            if dct.has_key('_attrib'):
                for (key, value) in dct['_attrib'].items():
                    if value is not CaseBlock.undefined:
                        block.set(key, fmt(value))
            if dct.has_key('_text'):
                block.text = unicode(dct['_text'])

            for (key, value) in sorted(dct.items(), key=sort_key):
                if value is not CaseBlock.undefined and not key.startswith('_'):
                    elem = ElementTree.Element(key)
                    block.append(elem)
                    if isinstance(value, dict):
                        dict_to_xml(elem, value)
                    else:
                        elem.text = fmt(value)
        dict_to_xml(case, self)
        return case

    def as_string(self, format_datetime=None):
        return ElementTree.tostring(self.as_xml(format_datetime))


class CaseBlockError(Exception):
    pass
