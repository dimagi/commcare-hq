from __future__ import absolute_import

from __future__ import unicode_literals
from xml.etree import cElementTree as ElementTree

from eulxml.xmlmap import (DateTimeField, IntegerField, NodeField, StringField,
                           XmlObject, load_xmlobject_from_string)

from casexml.apps.stock.const import (COMMTRACK_REPORT_XMLNS,
                                      REPORT_TYPE_BALANCE,
                                      REPORT_TYPE_TRANSFER)


class LedgerXML(XmlObject):
    """https://github.com/dimagi/commcare-core/wiki/ledgerxml
    """

    def as_xml(self):
        return ElementTree.fromstring(self.serialize())

    @classmethod
    def from_xml(cls, node):
        return load_xmlobject_from_string(ElementTree.tostring(node), cls)

    def as_string(self):
        return self.serialize()


class Value(LedgerXML):
    ROOT_NAME = 'value'
    section_id = StringField('@section-id', required=False)
    quantity = IntegerField('@quantity', required=True)


class Entry(LedgerXML):
    ROOT_NAME = 'entry'

    id = StringField('@id', required=True)
    section_id = StringField('@section-id', required=False)
    quantity = IntegerField('@quantity', required=True)

    value = NodeField('value', Value, required=False)


class Balance(LedgerXML):
    """https://github.com/dimagi/commcare-core/wiki/ledgerxml#balance-transactions
    """
    ROOT_NAME = REPORT_TYPE_BALANCE
    ROOT_NS = COMMTRACK_REPORT_XMLNS

    entity_id = StringField('@entity-id', required=True)
    date = DateTimeField('@date', required=True)
    section_id = StringField('@section-id', required=False)

    entry = NodeField('entry', Entry, required=True)


class Transfer(LedgerXML):
    """https://github.com/dimagi/commcare-core/wiki/ledgerxml#transfer-transactions
    """
    ROOT_NAME = REPORT_TYPE_TRANSFER
    ROOT_NS = COMMTRACK_REPORT_XMLNS

    src = StringField('@src', required=False)
    dest = StringField('@dest', required=False)
    date = DateTimeField('@date', required=True)
    type = StringField('@type', required=False)
    section_id = StringField('@section-id', required=False)

    entry = NodeField('entry', Entry, required=True)
