from __future__ import absolute_import
import copy
from datetime import datetime
from xml.etree import ElementTree
from dimagi.utils.parsing import json_format_datetime
from casexml.apps.case.xml import V1, NS_VERSION_MAP, V2
from casexml.apps.case.xml.generator import date_to_xml_string


class CaseBlock(dict):
    """
    Doctests:

    >>> NOW = datetime(year=2012, month=1, day=24)
    >>> FIVE_DAYS_FROM_NOW = datetime(year=2012, month=1, day=29)
    >>> CASE_ID = 'test-case-id'

    # Basic
    >>> ElementTree.tostring(CaseBlock(
    ...     case_id=CASE_ID,
    ...     date_opened=NOW,
    ...     date_modified=NOW,
    ... ).as_xml())
    '<case><case_id>test-case-id</case_id><date_modified>2012-01-24</date_modified><update><date_opened>2012-01-24</date_opened></update></case>'

    # Doesn't let you specify a keyword twice (here 'case_name')
    >>> try:
    ...     CaseBlock(
    ...         case_id=CASE_ID,
    ...         case_name='Johnny',
    ...         update={'case_name': 'Johnny'},
    ...     ).as_xml()
    ... except CaseBlockError, e:
    ...     print "%s" % e
    Key 'case_name' specified twice

    # The following is a BUG; should fail!! Should fix and change tests
    >>> ElementTree.tostring(CaseBlock(
    ...     case_id=CASE_ID,
    ...     date_opened=NOW,
    ...     date_modified=NOW,
    ...     update={
    ...         'date_opened': FIVE_DAYS_FROM_NOW,
    ...     },
    ... ).as_xml())
    '<case><case_id>test-case-id</case_id><date_modified>2012-01-24</date_modified><update><date_opened>2012-01-24</date_opened></update></case>'

    """
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
            # referrals currently not supported
            # V2 only
            index=None,
            version=V1,
            compatibility_mode=False,
        ):
        """
        From https://bitbucket.org/javarosa/javarosa/wiki/casexml

        <case>
            <case_id/>        <-- Exactly One: The id of the abstract case to be modified (even in the case of creation)
            <date_modified/>  <-- Exactly One: The date of this operation

            <create>         <-- At Most One: Create action
                <case_type_id/>             <-- Exactly One: The ID for the type of case represented
                <user_id/>                  <-- At Most One: The ID for a user who created the case
                <case_name/>                <-- Exactly One: A semantically meaningless but human readable name associated with the case
                <external_id/>              <-- Exactly One: The soft id associated with this record. Generally based on another system's id for this record.
            </create>

            <update/>         <-- At Most One: Updates data for the case
                <case_type_id/>             <-- At Most One: Modifies the Case Type for the case
                <case_name/>                <-- At Most One: A semantically meaningless but human readable name associated with the case
                <date_opened/>              <-- At Most One: Modifies the Date the case was opened
                <*/>                        <-- An Arbitrary Number: Creates or mutates a value identified by the key provided
            </update>

            <close/>          <-- At Most One: Closes the case

#            <referral>       <-- At Most One: Referral actions
#                <referral_id/>              <-- Exactly One: The unique ID. No two referrals should be open with both the same referral_id and referral_type
#                <followup_date/>            <-- At Most One: The due date for all followups referenced in this action
#                <open>
#                    <referral_types/>       <-- Exactly One: A space separated list of referral types which should be opened.
#                </open>
#                <update>
#                    <referral_type/>        <-- Exactly One: The referral type to be changed
#                    <date_closed/>          <-- At Most One: The date the referral was closed. If this element exists, the abstract referral matching the referral_id and referral_type should be closed.
#                </update>
#            </referral>
        </case>

        https://bitbucket.org/commcare/commcare/wiki/casexml20

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
        date_modified = date_modified or datetime.utcnow()
        update = copy.copy(update) if update else {}
        index = copy.copy(index) if index else {}

        self.XMLNS = NS_VERSION_MAP.get(version)

        if version == V1:
            self.VERSION = V1
            self.CASE_TYPE = "case_type_id"
        elif version == V2:
            self.VERSION = V2
            self.CASE_TYPE = "case_type"
        else:
            raise CaseBlockError("Case XML version must be %s or %s" % (V1, V2))

        if create:
            self['create'] = {}
            # make case_type
            case_type = "" if case_type is CaseBlock.undefined else case_type
            case_name = "" if case_name is CaseBlock.undefined else case_name
            if version == V2:
                owner_id = "" if owner_id is CaseBlock.undefined else owner_id
        self['update'] = update
        self['update'].update({
            'date_opened':                  date_opened
        })
        create_or_update = {
            self.CASE_TYPE:                 case_type,
            'case_name':                    case_name,
        }

        # what to do with case_id, date_modified, user_id, and owner_id, external_id
        if version == V1:
            self.update({
                'case_id':                  case_id, # V1
                'date_modified':            date_modified, # V1
            })
            if create:
                self['create'].update({
                    'user_id':              user_id, # V1
                })
            else:
                if not compatibility_mode and user_id is not CaseBlock.undefined:
                    CaseBlockError("CaseXML V1: You only set user_id when creating a case")
            self['update'].update({
                'owner_id':                 owner_id, # V1
            })
            create_or_update.update({
                'external_id':              external_id # V1
            })
        else:
            self.update({
                '_attrib': {
                    'case_id':              case_id, # V2
                    'date_modified':        date_modified, # V2
                    'user_id':              user_id, # V2
                    'xmlns':                self.XMLNS,
                }
            })
            create_or_update.update({
                'owner_id':                 owner_id, # V2
            })
            self['update'].update({
                'external_id':              external_id, # V2
            })


        # fail if user specifies both, say, case_name='Johnny' and update={'case_name': 'Johnny'}
        for key in create_or_update:
            if create_or_update[key] is not CaseBlock.undefined and self['update'].has_key(key):
                raise CaseBlockError("Key %r specified twice" % key)

        if create:
            self['create'].update(create_or_update)
        else:
            self['update'].update(create_or_update)


        if close:
            self['close'] = {}

        if not ['' for val in self['update'].values() if val is not CaseBlock.undefined]:
                self['update'] = CaseBlock.undefined
        if index and version == V2:
            self['index'] = {}
            for name, (case_type, case_id) in index.items():
                self['index'][name] = {
                    '_attrib': {
                        'case_type': case_type
                    },
                    '_text': case_id
                }

    def as_xml(self, format_datetime=date_to_xml_string):
        format_datetime = format_datetime or json_format_datetime
        case = ElementTree.Element('case')
        order = ['case_id', 'date_modified', 'create', 'update', 'close',
                 self.CASE_TYPE, 'user_id', 'case_name', 'external_id', 'date_opened', 'owner_id']
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
            elif isinstance(value, (basestring, int)):
                return unicode(value)
            else:
                raise CaseBlockError("Can't transform to XML: %s; unexpected type." % value)

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

    def as_string(self, format_datetime=date_to_xml_string):
        return ElementTree.tostring(self.as_xml(format_datetime))


class CaseBlockError(Exception):
    pass
