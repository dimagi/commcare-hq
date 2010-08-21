import logging, sys, traceback

from receiver.models import SubmissionHandlingType

# some constants used by the submission handler
APP_NAME = "phone"
REGISTRATION_HANDLER = "registration_response"
BACKUP_HANDLER = "backup_response"

# xmlns that registrations and backups come in as, respectively. 
REGISTRATION_XMLNS = "http://openrosa.org/user-registration"
BACKUP_XMLNS = "http://www.commcarehq.org/backup"

def create_backup(attachment):
    """Create a backup from a file and attachment"""
    # for the time being, this needs to be in here because of cyclical 
    # references
    from phone.backup import create_backup_objects
    create_backup_objects(attachment)
    
    # also tell the submission it was handled, so we can override the custom response
    handle_type = SubmissionHandlingType.objects.get_or_create(app=APP_NAME, method=BACKUP_HANDLER)[0]
    attachment.submission.handled(handle_type)
    
def create_phone_user(attachment):
    """Create a phone user from a file and attachment"""
    from phone.registration import create_registration_objects
    try:
        create_registration_objects(attachment)
        
        # also tell the submission it was handled, so we can override the custom response
        handle_type = SubmissionHandlingType.objects.get_or_create(app=APP_NAME, 
                                                                   method=REGISTRATION_HANDLER)[0]
        attachment.submission.handled(handle_type)
    except Exception, e:
        type, value, tb = sys.exc_info()
        traceback_string = "\n\nTRACEBACK: " + '\n'.join(traceback.format_tb(tb))
        logging.error(unicode(traceback_string))
