import logging
from xml.etree import ElementTree

from receiver.models import SubmissionHandlingType

# some constants used by the submission handler
BACKUP_HANDLER = "backup_response"
APP_NAME = "backups"

# some constants used by the backup xml parser and routing
BACKUP_XMLNS = "http://www.commcarehq.org/backup"
PROPERTIES_TAG = "properties"
DEVICE_ID_TAG = "device-id"
USERS_TAG = "users"
USERNAME_TAG = "name"

def create_backup(attachment):
    """Create a backup from a file and attachment"""
    # for the time being, this needs to be in here because of cyclical 
    # references
    from backups.models import Backup, BackupUser
    backup = Backup(attachment=attachment)
    usernames, device_id = _get_backup_metadata(attachment)
    backup.device_id = device_id
    backup.save()
    domain = attachment.submission.domain
    users = []
    for username in usernames:
        users.append(BackupUser.objects.get_or_create(domain=domain, 
                                                      username=username)[0])
    backup.users = users
    backup.save()
    
    # also tell the submission it was handled, so we can override the custom response
    handle_type = SubmissionHandlingType.objects.get_or_create(app=APP_NAME, method=BACKUP_HANDLER)[0]
    attachment.submission.handled(handle_type)
    
def _get_backup_metadata(attachment):
    """Gets the users, device_id, and whatever else we desire to extract from 
       a  backup file."""
    xml_payload = attachment.get_contents()
    element = ElementTree.XML(xml_payload)
    props_tag = _get_tag(BACKUP_XMLNS, PROPERTIES_TAG)
    device_tag = _get_tag(BACKUP_XMLNS, DEVICE_ID_TAG)
    users_tag = _get_tag(BACKUP_XMLNS, USERS_TAG)
    username_tag = _get_tag(BACKUP_XMLNS, USERNAME_TAG)
    props_elem = element.find(props_tag)
    # we assume the xml is like <root><properties><device-id>asdlfkjasld</device-id>...</root>
    
    # this is obnoxious - find seems to only work for top-level nodes
    # so walk through the properties searching for the tag we want
    errors = []
    for child in props_elem:
        if device_tag == child.tag:
            device_id = child.text
    if not device_id:
        errors.append("no device id found")
        
    users_elem = element.find(users_tag)
    usernames = []
    for user_elem in users_elem:
        for user_val in user_elem:
            if username_tag == user_val.tag:
                usernames.append(user_val.text)
    if not usernames:
        errors.append("no usernames found in")
    if errors:
        error_string = " and ".join(errors) + " in xml backup file: %s" % attachment
        logging.error(error_string)
        raise Exception(error_string)
    return [usernames, device_id]

def _get_tag(xmlns, tag):
    # this is odd, but our python xml libraries seem to want to name things like:
    # {http://www.commcarehq.org/backup}sometag
    return "{%s}%s" % (xmlns, tag)