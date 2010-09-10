from __future__ import absolute_import

import datetime
from django.conf import settings
from couchdbkit.ext.django.schema import *
import couchforms.const as const
from dimagi.utils.parsing import string_to_datetime
from couchdbkit.schema.properties_proxy import SchemaListProperty
from couchforms.safe_index import safe_index
from xml.etree import ElementTree
from django.utils.datastructures import SortedDict
from couchdbkit.resource import ResourceNotFound
import logging
import hashlib

"""
Couch models.  For now, we prefix them starting with C in order to 
differentiate them from their (to be removed) django counterparts.
"""


class Metadata(object):
    """
    Metadata of an xform, from a meta block structured like:
        
        <Meta>
            <clinic_id />
            <TimeStart />
            <TimeEnd />
            <username />
            <user_id />
            <uid />
        </Meta>
    
    Everything is optional.
    """
    """
    clinic_id = StringProperty()
    time_start = DateTimeProperty()
    time_end = DateTimeProperty()
    username = StringProperty()
    user_id = StringProperty()
    uid = StringProperty()
    """
    clinic_id = None
    time_start = None
    time_end = None
    username = None
    user_id = None
    uid = None

    def __init__(self, meta_block):
        if const.TAG_META_CLINIC_ID in meta_block:
            self.clinic_id = str(meta_block[const.TAG_META_CLINIC_ID])
        if const.TAG_META_TIMESTART in meta_block:
            self.time_start = string_to_datetime(meta_block[const.TAG_META_TIMESTART])
        elif "time_start" in meta_block:
            self.time_start = string_to_datetime(meta_block["time_start"])
        if const.TAG_META_TIMEEND in meta_block:
            self.time_end = string_to_datetime(meta_block[const.TAG_META_TIMEEND])
        elif "time_end" in meta_block:
            self.time_end = string_to_datetime(meta_block["time_end"])
        if const.TAG_META_USERNAME in meta_block:
            self.username = meta_block[const.TAG_META_USERNAME]
        if const.TAG_META_USER_ID in meta_block:
            self.user_id = meta_block[const.TAG_META_USER_ID]
        if const.TAG_META_UID in meta_block:
            self.uid = meta_block[const.TAG_META_UID]
    
    def to_dict(self):
        return dict([(key, getattr(self, key)) for key in \
                     ("clinic_id", "time_start", "time_end",
                      "username", "user_id","uid")])

class CXFormInstance(Document):
    """An XForms instance."""
    
    @property
    def type(self):
        return self.all_properties().get(const.TAG_TYPE, "")
        
    @property
    def version(self):
        return self.all_properties().get(const.TAG_VERSION, "")
        
    @property
    def uiversion(self):
        return self.all_properties().get(const.TAG_UIVERSION, "")
    
    @property
    def namespace(self):
        return self.all_properties().get(const.TAG_NAMESPACE, "")
    
    @property
    def metadata(self):
        if (const.TAG_META) in self.all_properties():
            meta_block = self.all_properties()[const.TAG_META]
            meta = Metadata(meta_block)
            return meta
            
        return None
        
    def __unicode__(self):
        return "%s (%s)" % (self.type, self.namespace)

    def xpath(self, path):
        """
        Evaluates an xpath expression like: path/to/node and returns the value 
        of that element, or None if there is no value.
        """
        return safe_index(self, path.split("/"))
    
        
    def found_in_multiselect_node(self, xpath, option):
        """
        Whether a particular value was found in a multiselect node, referenced
        by path.
        """
        node = self.xpath(xpath)
        return node and option in node.split(" ")
    
    def get_xml(self):
        try:
            # new way to get attachments
            return self.fetch_attachment("form.xml")
        except ResourceNotFound:
            logging.warn("no xml found for %s, trying old attachment scheme." % self.get_id)
            return self[const.TAG_XML]
    
    def xml_md5(self):
        return hashlib.md5(self.get_xml()).hexdigest()
    
    def top_level_tags(self):
        """
        Get the top level tags found in the xml, in the order they are found.
        """
        xml_payload = self.get_xml()
        element = ElementTree.XML(xml_payload)
        to_return = SortedDict()
        for child in element:
            # fix {namespace}tag format forced by ElementTree in certain cases (eg, <reg> instead of <n0:reg>)
            key = child.tag.split('}')[1] if child.tag.startswith("{") else child.tag 
            to_return[key] = self.xpath(key)
        return to_return
