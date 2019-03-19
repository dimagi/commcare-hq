from __future__ import absolute_import
from __future__ import unicode_literals
import settings
from casexml.apps.case.xml import V1, V2, V3, check_version, V2_NAMESPACE
from xml.etree import cElementTree as ElementTree
import logging
from dimagi.utils.parsing import json_format_datetime, json_format_date
from dateutil.parser import parse as parse_datetime

from corehq.toggles import MM_CASE_PROPERTIES
from corehq.util.quickcache import quickcache
import six


def datetime_to_xml_string(datetime_string):
    if isinstance(datetime_string, bytes):
        datetime_string = datetime_string.decode('utf-8')
    if isinstance(datetime_string, six.text_type):
        return datetime_string

    return json_format_datetime(datetime_string)


def safe_element(tag, text=None):
    # shortcut for commonly used functionality
    # bad! copied from the phone's XML module
    if text:
        e = ElementTree.Element(tag)
        e.text = six.text_type(text)
        return e
    else:
        return ElementTree.Element(tag)


def date_to_xml_string(date):
    if not date:
        return ''

    if isinstance(date, bytes):
        date = date.decode('utf-8')
    if isinstance(date, six.text_type):
        date = parse_datetime(date)

    return json_format_date(date)


def get_dynamic_element(key, val):
    """
    Gets an element from a key/value pair assumed to be pulled from
    a case object (usually in the dynamic properties)
    """
    element = ElementTree.Element(key)
    if isinstance(val, dict):
        element.text = six.text_type(val.get('#text', ''))
        element.attrib = dict([(x[1:], six.text_type(val[x])) for x in \
                               [x for x in val if x and x.startswith("@")]])
    else:
        # assume it's a string. Hopefully this is valid
        element.text = six.text_type(val)
    return element


class CaseXMLGeneratorBase(object):
    # The breakdown of functionality here is a little sketchy, but basically
    # everything that changed from v1 to v2 gets a split. The rest is
    # attempted to be as DRY as possible

    def __init__(self, case):
        self.case = case

    # Force subclasses to override any methods that we don't explictly
    # want to implement in the base class. However fill in a lot ourselves.
    def _ni(self):
        raise NotImplementedError("That method must be overridden by subclass!")

    def get_root_element(self):
        self._ni()

    def get_create_element(self):
        return safe_element("create")

    def get_update_element(self):
        return safe_element("update")

    def get_close_element(self):
        return safe_element("close")

    def get_index_element(self, index):
        elem = safe_element(index.identifier, index.referenced_id)
        elem.attrib = {"case_type": index.referenced_type}
        if getattr(index, 'relationship') and index.relationship == "extension":
            elem.attrib.update({"relationship": index.relationship})
        return elem

    def get_case_type_element(self):
        self._ni()

    def get_user_id_element(self):
        return safe_element("user_id", self.case.user_id)

    def get_case_name_element(self):
        return safe_element("case_name", self.case.name)

    def get_external_id_element(self):
        return safe_element("external_id", self.case.external_id)

    def add_base_properties(self, element):
        element.append(self.get_case_type_element())
        element.append(self.get_case_name_element())

    def add_custom_properties(self, element):
        for k, v, in self.case.dynamic_case_properties().items():
            element.append(get_dynamic_element(k, v))

    def add_indices(self, element):
        self._ni()


class V1CaseXMLGenerator(CaseXMLGeneratorBase):

    def get_root_element(self):
        root = safe_element("case")
        # moved to attrs in v2
        root.append(safe_element("case_id", self.case.case_id))
        if self.case.modified_on:
            root.append(safe_element("date_modified",
                                     datetime_to_xml_string(self.case.modified_on)))
        return root

    def get_case_type_element(self):
        return safe_element("case_type_id", self.case.type)

    def add_base_properties(self, element):
        element.append(self.get_case_type_element())
        # moved in v2
        element.append(self.get_user_id_element())
        element.append(self.get_case_name_element())
        # deprecated in v2
        element.append(self.get_external_id_element())

    def add_custom_properties(self, element):
        if self.case.owner_id:
            element.append(safe_element('owner_id', self.case.owner_id))
        if self.case.opened_on:
            element.append(safe_element('date_opened', date_to_xml_string(self.case.opened_on)))
        super(V1CaseXMLGenerator, self).add_custom_properties(element)

    def add_indices(self, element):
        # intentionally a no-op
        if self.case.indices:
            logging.info("Tried to add indices to version 1 CaseXML restore. This is not supported. "
                         "The case id is %s, domain %s." % (self.case.case_id, self.case.domain))

    def add_attachments(self, element):
        pass


class V2CaseXMLGenerator(CaseXMLGeneratorBase):

    def get_root_element(self):
        root = safe_element("case")
        root.attrib = {
            "xmlns": V2_NAMESPACE,
            "case_id": self.case.case_id,
            "user_id": self.case.user_id or '',
        }
        if self.case.modified_on:
            root.attrib["date_modified"] = datetime_to_xml_string(self.case.modified_on)
        return root

    def get_case_type_element(self):
        # case_type_id --> case_type
        return safe_element("case_type", self.case.type)

    def add_base_properties(self, element):
        super(V2CaseXMLGenerator, self).add_base_properties(element)
        from corehq.apps.users.cases import get_owner_id
        element.append(safe_element('owner_id', get_owner_id(self.case)))

    def add_custom_properties(self, element):
        if self.case.external_id:
            element.append(safe_element('external_id', self.case.external_id))
        if self.case.opened_on:
            element.append(safe_element("date_opened", date_to_xml_string(self.case.opened_on)))
        super(V2CaseXMLGenerator, self).add_custom_properties(element)

    def add_indices(self, element):
        if self.case.indices:
            indices = []
            index_elem = safe_element("index")
            for i in self.case.indices:
                indices.append(self.get_index_element(i))
            indices.sort(key=lambda elem: elem.tag)
            for index in indices:
                index_elem.append(index) # .extend() only works in python 2.7

            element.append(index_elem)

    def add_attachments(self, element):
        if _sync_attachments(self.case.domain):
            if self.case.case_attachments:
                attachment_elem = safe_element("attachment")
                for k, a in self.case.case_attachments.items():
                    aroot = safe_element(k)
                    # moved to attrs in v2
                    aroot.attrib = {
                        "src": self.case.get_attachment_server_url(k),
                        "from": "remote"
                    }
                    attachment_elem.append(aroot)
                element.append(attachment_elem)


@quickcache(['domain'],
            skip_arg=lambda _: settings.UNIT_TESTING,
            memoize_timeout=12 * 60 * 60,
            timeout=12 * 60 * 60)
def _sync_attachments(domain):
    return MM_CASE_PROPERTIES.enabled(domain)


def get_generator(version, case):
    check_version(version)
    return GENERATOR_MAP[version](case)

GENERATOR_MAP = {
    V1: V1CaseXMLGenerator,
    V2: V2CaseXMLGenerator,
    V3: V2CaseXMLGenerator
}


class CaseDBXMLGenerator(V2CaseXMLGenerator):

    def __init__(self, case):
        self.case = case

    def get_root_element(self):
        from corehq.apps.users.cases import get_owner_id
        root = safe_element("case")
        root.attrib = {
            "case_id": self.case.case_id,
            "case_type": self.case.type,
            "owner_id": get_owner_id(self.case),
            "status": "closed" if self.case.closed else "open",
        }
        return root

    def add_base_properties(self, element):
        element.append(self.get_case_name_element())
        if self.case.modified_on:
            element.append(safe_element("last_modified", datetime_to_xml_string(self.case.modified_on)))

    def get_element(self):
        element = self.get_root_element()
        self.add_base_properties(element)
        self.add_custom_properties(element)
        self.add_indices(element)
        self.add_attachments(element)
        return element
