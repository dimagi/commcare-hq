import logging
from xml.etree import ElementTree

from phone.xmlutils import get_tag
from phone.models import PhoneBackup, Phone
from phone.processor import BACKUP_XMLNS

# some constants used by the xml parser 
PROPERTIES_TAG = "properties"
DEVICE_ID_TAG = "device-id"
USERS_TAG = "users"
USERNAME_TAG = "name"

'''
Module for managing backups
'''
def create_backup_objects(attachment):
    # TODO: should finding new users in a backup file register them?
    backup = PhoneBackup(attachment=attachment)
    device_id = _get_backup_device_id(attachment)
    backup.phone = Phone.objects.get_or_create(device_id=device_id,
                                               domain = attachment.submission.domain)[0]
    print "phone is: %s" % backup.phone
    backup.save()
    
    
def _get_backup_device_id(attachment):
    """Gets the users, device_id, and whatever else we desire to extract from 
       a  backup file."""
    xml_payload = attachment.get_contents()
    element = ElementTree.XML(xml_payload)
    props_tag = get_tag(BACKUP_XMLNS, PROPERTIES_TAG)
    device_tag = get_tag(BACKUP_XMLNS, DEVICE_ID_TAG)
    props_elem = element.find(props_tag)
    # we assume the xml is like <root><properties><device-id>asdlfkjasld</device-id>...</root>
    
    # this is obnoxious - find seems to only work for top-level nodes
    # so walk through the properties searching for the tag we want
    device_id = None
    for child in props_elem:
        if device_tag == child.tag:
            device_id = child.text
    if not device_id:
        raise Exception("no device id found")
    return device_id
    
    